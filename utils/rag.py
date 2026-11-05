"""Medical report RAG data layer: extract -> chunk -> embed -> store -> search.

No Streamlit imports (easy to test). The embedding function is injected, so tests
can run without the network.
"""
from __future__ import annotations

import io
import re
from typing import Callable

EMBED_DIM = 768  # must match vector(768) in db/migrations/003_report_rag.sql
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PAGES = 60
MAX_CHARS = 60_000
CHUNK_CHARS = 900
OVERLAP_CHARS = 150
BATCH = 50

EmbedFn = Callable[[list[str], str], list[list[float]]]  # (texts, task_type) -> vectors


# ---------- Extraction ----------
def extract_text(filename: str, data: bytes) -> str:
    """Text from a .txt or .pdf upload. Raises ValueError with a user-friendly message."""
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("File is larger than 5 MB. Paste the important parts as text instead.")
    name = filename.lower()
    if name.endswith(".txt"):
        for enc in ("utf-8-sig", "cp1256", "latin-1"):  # cp1256 = common Arabic Windows encoding
            try:
                return clean_text(data.decode(enc))
            except UnicodeDecodeError:
                continue
    if name.endswith(".pdf"):
        return _pdf_text(data)
    raise ValueError("Only .pdf and .txt files are supported.")


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader  # lazy: only needed for PDFs

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("This PDF is password-protected. Remove the password and retry.")
        pages = reader.pages[:MAX_PAGES]
        text = "\n\n".join((p.extract_text() or "") for p in pages)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Couldn't read this PDF ({type(e).__name__}). Try pasting the text.") from e
    text = clean_text(text)
    if len(text) < 30:
        raise ValueError(
            "No text found. This looks like a scanned PDF (images only). "
            "OCR isn't supported yet: paste the text of the report instead."
        )
    return text


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------- Chunking ----------
_SENTENCE_END = re.compile(r"(?<=[.!?؟۔])\s+")


def _pieces(text: str, max_chars: int) -> list[str]:
    """Paragraphs, with oversized ones split by sentence, then hard-wrapped by words."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            out.append(para)
            continue
        buf = ""
        for sent in _SENTENCE_END.split(para):
            while len(sent) > max_chars:  # no punctuation at all: cut at a space
                cut = sent.rfind(" ", 0, max_chars)
                cut = cut if cut > max_chars // 2 else max_chars
                if buf:
                    out.append(buf)
                    buf = ""
                out.append(sent[:cut].strip())
                sent = sent[cut:].strip()
            if buf and len(buf) + 1 + len(sent) > max_chars:
                out.append(buf)
                buf = sent
            else:
                buf = f"{buf} {sent}".strip()
        if buf:
            out.append(buf)
    return out


def _tail(text: str, n: int) -> str:
    """Last ~n chars of text, starting at a word boundary."""
    if len(text) <= n:
        return text
    tail = text[-n:]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < n // 2 else tail


def chunk_text(text: str, max_chars: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Paragraph-aware chunks of at most ~max_chars (plus overlap) with context carried over."""
    chunks: list[str] = []
    cur = ""
    for piece in _pieces(clean_text(text), max_chars):
        if cur and len(cur) + 1 + len(piece) > max_chars:
            chunks.append(cur)
            cur = f"{_tail(cur, overlap)}\n{piece}"
        else:
            cur = f"{cur}\n{piece}" if cur else piece
    if cur.strip():
        chunks.append(cur)
    return chunks


# ---------- Storage ----------
def _vec(v: list[float]) -> str:
    """pgvector text format; safest way to send a vector through PostgREST."""
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def index_report(client, user_id: str, title: str, text: str, embed: EmbedFn) -> tuple[str, int]:
    """Chunk + embed + save. Returns (report_id, n_chunks).

    Embeds BEFORE writing anything, so an API failure leaves nothing behind; if a later
    insert fails the report row is removed (chunks cascade).
    """
    text = clean_text(text)[:MAX_CHARS]
    if len(text) < 30:
        raise ValueError("The report text is too short to index.")
    chunks = chunk_text(text)
    vectors: list[list[float]] = []
    for i in range(0, len(chunks), BATCH):
        vectors += embed(chunks[i : i + BATCH], "RETRIEVAL_DOCUMENT")
    if len(vectors) != len(chunks) or any(len(v) != EMBED_DIM for v in vectors):
        raise RuntimeError("Embedding service returned unexpected vectors.")

    rep = (
        client.table("medical_reports")
        .insert({"user_id": user_id, "title": (title or "").strip() or "Medical report", "content": text})
        .execute()
    )
    report_id = rep.data[0]["id"]
    try:
        rows = [
            {
                "report_id": report_id,
                "user_id": user_id,
                "chunk_index": i,
                "content": c,
                "embedding": _vec(v),
            }
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ]
        for i in range(0, len(rows), BATCH):
            client.table("report_chunks").insert(rows[i : i + BATCH]).execute()
    except Exception:
        client.table("medical_reports").delete().eq("id", report_id).execute()
        raise
    return report_id, len(chunks)


def list_reports(client) -> list[dict]:
    rows = (
        client.table("medical_reports")
        .select("id,title,created_at,content")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [
        {"id": r["id"], "title": r.get("title") or "Medical report",
         "created_at": r.get("created_at"), "chars": len(r.get("content") or "")}
        for r in rows
    ]


def delete_report(client, report_id: str) -> None:
    client.table("medical_reports").delete().eq("id", report_id).execute()  # chunks cascade


# ---------- Retrieval ----------
def search(client, queries: list[str] | str, embed: EmbedFn, k: int = 5,
           report_id: str | None = None, max_total: int | None = None) -> list[dict]:
    """Top-k chunks per query, de-duplicated (best similarity wins), best first."""
    qs = [queries] if isinstance(queries, str) else list(queries)
    qs = [q.strip() for q in qs if q and q.strip()]
    if not qs:
        return []
    vectors = embed(qs, "RETRIEVAL_QUERY")
    best: dict[str, dict] = {}
    for vec in vectors:
        res = client.rpc(
            "match_report_chunks",
            {"query_embedding": _vec(vec), "match_count": k, "p_report_id": report_id},
        ).execute()
        for row in res.data or []:
            if row["id"] not in best or row["similarity"] > best[row["id"]]["similarity"]:
                best[row["id"]] = row
    ranked = sorted(best.values(), key=lambda r: r["similarity"], reverse=True)
    return ranked[:max_total] if max_total else ranked


# Queries that pull training-relevant facts out of a report (English + Arabic terms)
TRAINING_QUERIES = [
    "injury, joint pain, back, knee, shoulder, limitations, exercises to avoid",
    "MRI X-ray findings disc herniation tear fracture arthritis التهاب انزلاق غضروفي",
    "heart, blood pressure, cardiac, ECG, cardiovascular القلب الضغط",
    "diabetes, blood sugar, glucose, HbA1c, cholesterol, thyroid السكر الكوليسترول",
    "doctor recommendations, restrictions on physical activity, surgery, medication توصيات الطبيب",
]

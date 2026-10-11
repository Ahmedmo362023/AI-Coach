import hashlib, io, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from utils import rag

DIM = rag.EMBED_DIM

def fake_embed(texts, task_type):
    """Deterministic bag-of-words hash embedding: similar words -> similar vectors."""
    out = []
    for t in texts:
        v = [0.0] * DIM
        for w in t.lower().split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1
        n = math.sqrt(sum(x*x for x in v)) or 1
        out.append([x/n for x in v])
    return out

class Res:
    def __init__(self, data): self.data = data
class Q:
    def __init__(self, db, name): self.db, self.name, self.op, self.f = db, name, None, {}
    def insert(self, rows):
        self.op = "insert"; self.rows = rows if isinstance(rows, list) else [rows]; return self
    def delete(self): self.op = "delete"; return self
    def select(self, *_): self.op = "select"; return self
    def eq(self, k, v): self.f[k] = v; return self
    def order(self, *_, **__): return self
    def execute(self):
        t = self.db.tables.setdefault(self.name, [])
        if self.op == "insert":
            if self.db.fail_on == self.name: raise RuntimeError("boom")
            out = []
            for r in self.rows:
                r = {**r, "id": f"{self.name}-{len(t)+1}"}; t.append(r); out.append(r)
            return Res(out)
        if self.op == "delete":
            for r in [r for r in t if all(r.get(k) == v for k, v in self.f.items())]:
                t.remove(r)
                if self.name == "medical_reports":  # cascade
                    c = self.db.tables.get("report_chunks", [])
                    c[:] = [x for x in c if x["report_id"] != r["id"]]
            return Res([])
        return Res(list(t))
class RPC:
    def __init__(self, db, args): self.db, self.args = db, args
    def execute(self):
        qv = [float(x) for x in self.args["query_embedding"].strip("[]").split(",")]
        rows = []
        for c in self.db.tables.get("report_chunks", []):
            if self.args["p_report_id"] and c["report_id"] != self.args["p_report_id"]: continue
            cv = [float(x) for x in c["embedding"].strip("[]").split(",")]
            rows.append({"id": c["id"], "report_id": c["report_id"], "chunk_index": c["chunk_index"],
                         "content": c["content"], "similarity": sum(a*b for a, b in zip(qv, cv))})
        rows.sort(key=lambda r: -r["similarity"])
        return Res(rows[: self.args["match_count"]])
class FakeClient:
    def __init__(self, fail_on=None): self.tables, self.fail_on = {}, fail_on
    def table(self, n): return Q(self, n)
    def rpc(self, name, args): assert name == "match_report_chunks"; return RPC(self, args)

AR = "الأشعة بتقول إن فيه انزلاق غضروفي بسيط في الفقرة القطنية. ممنوع الأوزان التقيلة على الضهر. " * 30
EN = ("MRI of the right knee shows a partial tear of the medial meniscus.\n\n"
      "Blood pressure was 150/95. Recommend cardiology review before intense exercise.\n\n") * 15

def test_chunks_bounded_and_overlap():
    cs = rag.chunk_text(EN)
    assert len(cs) > 1
    assert all(len(c) <= rag.CHUNK_CHARS + rag.OVERLAP_CHARS + 5 for c in cs)
    assert "meniscus" in cs[0]

def test_chunks_arabic_and_no_punctuation_wall():
    assert len(rag.chunk_text(AR)) > 1
    wall = "كلمة " * 1000  # no sentence punctuation at all
    cs = rag.chunk_text(wall)
    assert all(len(c) <= rag.CHUNK_CHARS + rag.OVERLAP_CHARS + 5 for c in cs)

def test_short_text_one_chunk():
    assert rag.chunk_text("Short report text.") == ["Short report text."]

def test_txt_extract_encodings():
    assert "انزلاق" in rag.extract_text("a.txt", "انزلاق غضروفي".encode("utf-8"))
    assert "انزلاق" in rag.extract_text("a.TXT", "انزلاق غضروفي".encode("cp1256"))

def test_bad_type_and_size():
    with pytest.raises(ValueError): rag.extract_text("a.docx", b"x")
    with pytest.raises(ValueError): rag.extract_text("a.pdf", b"x" * (rag.MAX_FILE_BYTES + 1))

def _pdf(text=None):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf)
    if text: c.drawString(72, 750, text)
    c.showPage(); c.save(); return buf.getvalue()

def test_pdf_text_and_scanned():
    assert "meniscus" in rag.extract_text("r.pdf", _pdf("MRI shows a partial tear of the medial meniscus."))
    with pytest.raises(ValueError, match="scanned"): rag.extract_text("r.pdf", _pdf())
    with pytest.raises(ValueError): rag.extract_text("r.pdf", b"not a pdf at all")

def test_index_and_search_roundtrip():
    c = FakeClient()
    rid, n = rag.index_report(c, "u1", " Knee ", EN, fake_embed)
    assert n == len(c.tables["report_chunks"]) > 1
    assert c.tables["medical_reports"][0]["title"] == "Knee"
    assert all(r["user_id"] == "u1" and r["embedding"].startswith("[") for r in c.tables["report_chunks"])
    hits = rag.search(c, "meniscus tear knee", fake_embed, k=3)
    assert hits and "meniscus" in hits[0]["content"]
    assert hits == sorted(hits, key=lambda h: -h["similarity"])

def test_search_dedup_multi_query_and_scope():
    c = FakeClient()
    r1, _ = rag.index_report(c, "u1", "A", EN, fake_embed)
    r2, _ = rag.index_report(c, "u1", "B", AR, fake_embed)
    hits = rag.search(c, ["meniscus knee", "meniscus tear"], fake_embed, k=3)
    assert len({h["id"] for h in hits}) == len(hits)  # no duplicates
    scoped = rag.search(c, "meniscus", fake_embed, k=5, report_id=r2)
    assert scoped and all(h["report_id"] == r2 for h in scoped)
    assert len(rag.search(c, ["a", "b", "c"], fake_embed, k=5, max_total=2)) <= 2
    assert rag.search(c, ["", "  "], fake_embed) == []

def test_embed_failure_writes_nothing():
    c = FakeClient()
    def bad(texts, t): raise RuntimeError("api down")
    with pytest.raises(RuntimeError): rag.index_report(c, "u1", "x", EN, bad)
    assert not c.tables.get("medical_reports")

def test_chunk_insert_failure_rolls_back_report():
    c = FakeClient(fail_on="report_chunks")
    with pytest.raises(RuntimeError): rag.index_report(c, "u1", "x", EN, fake_embed)
    assert c.tables["medical_reports"] == [] and not c.tables.get("report_chunks")

def test_wrong_dims_rejected_and_too_short():
    with pytest.raises(RuntimeError): rag.index_report(FakeClient(), "u", "t", EN, lambda t, k: [[0.1]] * len(t))
    with pytest.raises(ValueError): rag.index_report(FakeClient(), "u", "t", "hi", fake_embed)

def test_delete_cascades_and_list():
    c = FakeClient()
    rid, _ = rag.index_report(c, "u1", "A", EN, fake_embed)
    assert rag.list_reports(c)[0]["title"] == "A"
    rag.delete_report(c, rid)
    assert not c.tables["medical_reports"] and not c.tables["report_chunks"]

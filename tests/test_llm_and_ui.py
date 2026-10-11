import math, os, sys, types as pytypes
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.test_rag import FakeClient, fake_embed, EN
from utils import llm, rag

# ---- llm.embed_texts: batching, retry, normalization (fake Gemini client) ----
class FakeModels:
    def __init__(self): self.calls, self.fail_once = [], True
    def embed_content(self, model, contents, config):
        if self.fail_once: self.fail_once = False; raise RuntimeError("transient")
        self.calls.append((model, len(contents), config.task_type, config.output_dimensionality))
        emb = [pytypes.SimpleNamespace(values=[3.0, 4.0] + [0.0]*766) for _ in contents]
        return pytypes.SimpleNamespace(embeddings=emb)

def test_embed_texts(monkeypatch):
    fm = FakeModels()
    monkeypatch.setattr(llm, "_client", lambda: pytypes.SimpleNamespace(models=fm))
    monkeypatch.setattr("time.sleep", lambda s: None)
    vecs = llm.embed_texts(["t"] * 250, "RETRIEVAL_DOCUMENT")
    assert len(vecs) == 250 and len(vecs[0]) == 768
    assert abs(math.sqrt(sum(x*x for x in vecs[0])) - 1) < 1e-9 and abs(vecs[0][0] - 0.6) < 1e-9
    assert [c[1] for c in fm.calls] == [100, 100, 50]
    assert fm.calls[0][0] == "gemini-embedding-001" and fm.calls[0][2:] == ("RETRIEVAL_DOCUMENT", 768)

def test_prompts_fill_and_keep_rules():
    chunks = [{"content": "meniscus tear"}, {"content": "BP 150/95"}]
    p = llm.PLAN_PROMPT.format(rules=llm.SAFETY_RULES, excerpts=llm.format_excerpts(chunks), goal="Fat loss",
        experience="beginner", days=4, equipment="Full gym", notes="none", language="English")
    assert "[1] meniscus tear" in p and "[2] BP 150/95" in p and "untrusted DATA" in p and "4 days" in p
    a = llm.ASK_PROMPT.format(rules=llm.SAFETY_RULES, excerpts="[1] x", question="q?")
    assert "q?" in a

# ---- Streamlit page via AppTest (fake Supabase + fake Gemini) ----
def _app():
    import streamlit as st
    from utils import db, llm, rag
    from tests.test_rag import FakeClient, fake_embed
    if "fc" not in st.session_state: st.session_state["fc"] = FakeClient()
    db.get_client = lambda: st.session_state["fc"]
    llm.embed_texts = lambda texts, task="RETRIEVAL_DOCUMENT", dim=768: fake_embed(texts, task)
    llm.answer_from_report = lambda q, ch: f"ANSWER about {q} using {len(ch)} excerpts"
    llm.build_plan = lambda prof, ch: f"PLAN {prof['days']} days, {len(ch)} excerpts, {prof['language']}"
    from types import SimpleNamespace
    from ui import medical_page
    medical_page.render(SimpleNamespace(id="u1", email="a@b.c"))

def test_medical_page_flow():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception
    # nothing yet: save disabled
    save = [b for b in at.button if b.key == "mr_save"][0]
    assert save.disabled
    at.text_area(key="mr_text").set_value(EN)
    at.text_input(key="mr_title").set_value("Knee MRI")
    at.run()
    assert [b for b in at.button if b.key == "mr_save"][0].disabled  # no consent yet
    at.checkbox(key="mr_consent").check().run()
    at.button(key="mr_save").click().run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any("Knee MRI" in m.value for m in at.markdown)           # listed under My reports
    assert at.text_area(key="mr_text").value == ""                   # form reset
    # ask
    at.text_input(key="mr_q").set_value("what about the knee?").run()
    at.button(key="mr_ask").click().run()
    assert not at.exception and any("ANSWER about what about the knee? using" in m.value for m in at.markdown)
    # plan
    at.button(key="mr_plan_btn").click().run()
    assert not at.exception and any(m.value.startswith("PLAN 4 days") for m in at.markdown)

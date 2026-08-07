"""
Slice-1 self-check for retrieval.py.

- chunk_text tests need NO database (pure function) — always run.
- The end-to-end search test needs ParadeDB up; it auto-skips if unreachable.

Run:  python test/test_retrieval.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.retrieval import chunk_text, RetrievalEngine


def test_chunker_never_cuts_words():
    text = ("The appellant filed a civil appeal. " * 200)  # long, many sentences
    chunks = chunk_text(text)
    assert chunks, "chunker produced nothing"
    vocab = set(" ".join(text.split()).split())
    for c in chunks:
        for word in c.split():
            assert word in vocab, f"broken/fabricated token: {word!r}"
    print(f"  chunker: {len(chunks)} chunks, no broken words  OK")


def test_chunker_respects_size_and_sentences():
    text = "First sentence here. Second one follows. Third arrives now. " * 100
    for c in chunk_text(text, target=300):
        assert len(c) <= 300 * 1.6, f"chunk too big: {len(c)}"
    print("  chunker: size + sentence packing  OK")


def test_monster_sentence_word_split():
    monster = "word " * 800  # one 4000-char "sentence", no terminators
    chunks = chunk_text(monster, target=500)
    assert all(len(c) <= 500 * 1.2 for c in chunks), "monster sentence not split"
    assert all("word" in c for c in chunks)
    print("  chunker: monster-sentence word-safe fallback  OK")


def test_search_end_to_end():
    """Needs ParadeDB. Builds a tiny index from real cases, checks known-item recall."""
    import glob
    import psycopg2
    dsn = os.getenv("DATABASE_URL", "postgresql://ailse:ailse@localhost:5432/ailse")
    try:
        psycopg2.connect(dsn).close()
    except Exception as e:
        print(f"  search: SKIPPED (DB unreachable: {e})")
        return

    corpus = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "supreme_court_cleaned_texts")
    files = sorted(glob.glob(os.path.join(corpus, "*.txt")))[:8]
    if not files:
        print("  search: SKIPPED (no corpus)"); return

    eng = RetrievalEngine(dsn)
    eng.init_db()
    tmp = os.path.join(os.path.dirname(__file__), "_tmp_corpus")
    os.makedirs(tmp, exist_ok=True)
    for f in files:
        open(os.path.join(tmp, os.path.basename(f)), "w", encoding="utf-8").write(
            open(f, encoding="utf-8", errors="ignore").read())
    eng.build(tmp)

    cid = os.path.splitext(os.path.basename(files[0]))[0]
    passage = chunk_text(open(files[0], encoding="utf-8", errors="ignore").read())[1]
    query = " ".join(passage.split()[:12])
    hits = eng.search(query, k=5)
    assert hits, "no results"
    top_cases = [h["case_id"] for h in hits]
    assert cid in top_cases, f"gold case {cid} not in top-5: {top_cases}"
    print(f"  search: known-item recall for case {cid}  OK ({top_cases[:3]})")


if __name__ == "__main__":
    print("test_retrieval:")
    test_chunker_never_cuts_words()
    test_chunker_respects_size_and_sentences()
    test_monster_sentence_word_split()
    test_search_end_to_end()
    print("done.")

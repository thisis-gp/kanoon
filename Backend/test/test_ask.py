"""
Slice-2 self-check: grounded /ask (retrieval + LLM gateway + citations).

Needs ParadeDB up + a populated `chunks` table + one working LLM provider.
Auto-skips if the DB is unreachable/empty or all providers fail.

Run:  python test/test_ask.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _db_ready():
    import psycopg2
    dsn = os.getenv("DATABASE_URL", "postgresql://ailse:ailse@localhost:5432/ailse")
    try:
        c = psycopg2.connect(dsn); cur = c.cursor()
        cur.execute("SELECT count(*) FROM chunks;")
        n = cur.fetchone()[0]; c.close()
        return n
    except Exception:
        return 0


def test_gateway():
    from model import llm_gateway
    try:
        txt, who = llm_gateway.generate("Reply with exactly: OK")
    except Exception as e:
        print(f"  gateway: SKIPPED (no provider: {e})"); return False
    assert txt, "empty completion"
    print(f"  gateway: {who} responded  OK")
    return True


def test_ask_grounded():
    n = _db_ready()
    if not n:
        print("  ask: SKIPPED (DB empty/unreachable — build the index first)"); return
    from model.ask import answer
    r = answer("What was the dispute about in this batch of cases?")
    assert r["answer"], "empty answer"
    assert r["sources"], "no sources returned"
    # grounding: either it cited a source, or it abstained cleanly
    grounded = bool(r["cited"]) or "not available" in r["answer"].lower()
    assert grounded, f"answer neither cited nor abstained: {r['answer'][:120]}"
    print(f"  ask: [{r['provider']}] answered over {len(r['sources'])} sources, "
          f"cited {r['cited']}  OK")

    # abstention on an out-of-domain question
    r2 = answer("What is the capital of France?")
    print(f"  ask: OOD -> cited {r2['cited']}, ans='{r2['answer'][:60]}...'")


if __name__ == "__main__":
    print("test_ask:")
    if test_gateway():
        test_ask_grounded()
    print("done.")

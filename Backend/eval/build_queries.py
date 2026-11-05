"""Build the known-item query set (fixed seed). Run INSIDE the backend container (needs DATABASE_URL).

  passage: first PASSAGE_WORDS words of the middle chunk of a case (cases with >= MIN_CHUNKS chunks)
  title:   the case title, only titles of the form "X vs Y" that are unique in case_meta and not truncated with an ellipsis

Gold = the case the query was derived from. The text is IN the index, so this is a PROXY and optimistic.
Usage: python build_queries.py OUT.jsonl [N_PER_TYPE]
"""
import json
import os
import random
import sys

import psycopg2

SEED = 20261104
PASSAGE_WORDS = 14
MIN_CHUNKS = 4
MIN_TITLE_WORDS, MAX_TITLE_WORDS = 3, 25
NA = "Not available"
TRUNCATION_MARKS = ("…", "...")  # titles cut by the metadata regex carry almost no information


def main(out_path, n):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    cur.execute("SELECT case_id FROM chunks GROUP BY case_id HAVING count(*) >= %s", (MIN_CHUNKS,))
    passage_cases = sorted(r[0] for r in cur.fetchall())
    cur.execute("SELECT case_id, title FROM case_meta WHERE title IS NOT NULL AND title <> %s", (NA,))
    titles = {}
    for cid, title in cur.fetchall():
        titles.setdefault(" ".join(title.split()).lower(), []).append((cid, title))
    title_pool = sorted(
        (v[0] for v in titles.values()
         if len(v) == 1 and " vs " in v[0][1] and MIN_TITLE_WORDS <= len(v[0][1].split()) <= MAX_TITLE_WORDS
         and not any(m in v[0][1] for m in TRUNCATION_MARKS)))

    rng = random.Random(SEED)
    rng.shuffle(passage_cases)
    rng.shuffle(title_pool)

    rows = []
    for cid in passage_cases[:n]:
        cur.execute("SELECT text FROM chunks WHERE case_id=%s ORDER BY id", (cid,))
        chunks = [r[0] for r in cur.fetchall()]
        q = " ".join(chunks[len(chunks) // 2].split()[:PASSAGE_WORDS])
        rows.append({"id": f"passage-{len(rows)}", "type": "passage", "query": q, "gold_case_id": cid})
    for cid, title in title_pool[:n]:
        rows.append({"id": f"title-{len(rows)}", "type": "title", "query": " ".join(title.split()), "gold_case_id": cid})

    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"passage pool={len(passage_cases)} title pool={len(title_pool)} written={len(rows)} -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 100)

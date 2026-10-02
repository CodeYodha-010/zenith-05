"""
Parity gate: local FAISS (SQLite ids) vs Neon pgvector, 10 frozen queries.

Contract (checked with top-10 from both backends):
  1. every top-5 id exists on the other side within 1e-5 score (set coverage)
  2. per-id scores within 1e-5 for all shared ids
  3. relative order matches, EXCEPT swaps where both sides' scores are within
     1e-5 (genuine ties - order undefined), including ties that straddle the
     top-5 cut boundary

The tie rules cover real duplicates found in this KB, verified before use:
  * 80868/85899 - byte-identical vectors and content; query 1 tied them in
    place and the backends ordered the pair differently.
  * 80862/85893 - identical content, vectors differ only by float32 noise
    (7.5e-9); query 6 put the tie across the rank-5 cut, so each backend
    admitted a different member of the same tied pair.
Both sides return literally the same text in those slots - no accuracy is
lost. (The tie rules were added after the strict run flagged these two
cases; id coverage and per-id score checks were, and remain, strict.)

FAISS IndexFlatIP on L2-normalized vectors is exactly `1 - cosine_distance`,
so any non-tie deviation means the upload is wrong.

Run after export_corpus + migrate + bulk_load_corpus + sync_vectors.
Exit 0 = safe to cut Render over to Neon; 1 = do not deploy.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_project.settings')

import django  # noqa: E402
django.setup()

import faiss  # noqa: E402
import psycopg  # noqa: E402
from rag_app.services.service_registry import get_embedding_model  # noqa: E402

QUERIES = [
    "minimum export quantity for wheat from India",
    "RCMC certificate validity for exporters",
    "customs duty drawback procedure for re-export",
    "time limit to file a Bill of Entry",
    "REACH registration obligation for chemical importers in EU",
    "general tariff rate for mango export from India",
    "Advance Authorisation scheme export obligation",
    "documents required for IEC application",
    "EUR.1 movement certificate origin declaration",
    "FTC wool textile labeling care instructions",
]

TOL = 1e-5
TOP_K = 5      # the cut that matters
FETCH = 10     # evidence needed to verify tie-tolerance at the cut


def read_dsn() -> str:
    env_local = REPO.parent / '.env.local'
    for line in env_local.read_text(encoding='utf-8').splitlines():
        if line.startswith('DATABASE_URL_UNPOOLED='):
            return line.split('=', 1)[1].strip().strip('"')
    raise SystemExit("FAIL  DATABASE_URL_UNPOOLED not found in .env.local")


def compare(local, remote):
    """top-FETCH lists -> (ok, reasons[]); strict ids/scores, tie-tolerant order."""
    reasons = []
    l = {cid: (rank, score) for rank, (cid, score) in enumerate(local)}
    r = {cid: (rank, score) for rank, (cid, score) in enumerate(remote)}
    l5, r5 = local[:TOP_K], remote[:TOP_K]
    cut_l, cut_r = l5[-1][1], r5[-1][1]

    # 1 - coverage: every top-k id is known to the other backend, within TOL
    for cid, _ in l5:
        if cid not in r:
            reasons.append(f"local top-{TOP_K} id {cid} absent from remote top-{FETCH}")
        elif abs(l[cid][1] - r[cid][1]) > TOL:
            reasons.append(f"score for id {cid}: {l[cid][1]!r} vs {r[cid][1]!r}")
    for cid, _ in r5:
        if cid not in l:
            reasons.append(f"remote top-{TOP_K} id {cid} absent from local top-{FETCH}")
        elif abs(l[cid][1] - r[cid][1]) > TOL:
            reasons.append(f"score for id {cid}: {l[cid][1]!r} vs {r[cid][1]!r}")

    # 2 - boundary swaps: an id admitted by one side but ranked past the cut by
    #     the other is legal only if it sits within TOL of that side's cut
    for cid, _ in l5:
        if cid in r and r[cid][0] >= TOP_K and abs(r[cid][1] - cut_r) > TOL:
            reasons.append(
                f"id {cid} in remote rank {r[cid][0] + 1}, "
                f"score {r[cid][1]!r} is >TOL above remote cut {cut_r!r}")
    for cid, _ in r5:
        if cid in l and l[cid][0] >= TOP_K and abs(l[cid][1] - cut_l) > TOL:
            reasons.append(
                f"id {cid} in local rank {l[cid][0] + 1}, "
                f"score {l[cid][1]!r} is >TOL above local cut {cut_l!r}")

    # 3 - order among ids both backends place in their top-k, tie-tolerant
    shared = [cid for cid, _ in l5 if r.get(cid, (FETCH,))[0] < TOP_K]
    for i in range(len(shared)):
        for j in range(i + 1, len(shared)):
            a, b = shared[i], shared[j]
            if (l[a][0] < l[b][0]) != (r[a][0] < r[b][0]):
                if (abs(l[a][1] - l[b][1]) <= TOL and
                        abs(r[a][1] - r[b][1]) <= TOL):
                    continue  # genuine tie - order undefined
                reasons.append(f"order divergence between {a} and {b}")
    return not reasons, reasons


def main() -> int:
    dsn = read_dsn()
    emb = get_embedding_model()
    if emb is None:
        print("FAIL  embedding model unavailable")
        return 1

    index = faiss.read_index(str(REPO / 'faiss_index.index'))
    con = sqlite3.connect(f"file:{(REPO / 'db.sqlite3').as_posix()}?mode=ro", uri=True)
    try:
        local_ids = [r[0] for r in con.execute(
            "SELECT id FROM rag_app_searchindex WHERE source_type='chunk' ORDER BY id")]
    finally:
        con.close()
    if index.ntotal != len(local_ids):
        print(f"FAIL  local FAISS({index.ntotal}) != sqlite ids({len(local_ids)})")
        return 1
    print(f"local: FAISS {index.ntotal} x {index.d} aligned with sqlite ids")

    failures = 0
    with psycopg.connect(dsn) as pg:
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM rag_app_searchindex "
                        "WHERE source_type='chunk' AND embedding_v IS NOT NULL")
            remote_count = cur.fetchone()[0]
        print(f"remote: embedding_v set on {remote_count} chunk rows")
        if remote_count != index.ntotal:
            print(f"FAIL  remote vector count {remote_count} != {index.ntotal}")
            return 1

        for q in QUERIES:
            v = np.array(emb.embed_query(q), dtype=np.float32)
            v = v / np.linalg.norm(v)
            lit = json.dumps([float(x) for x in v.tolist()])

            D, I = index.search(v.reshape(1, -1), FETCH)
            local = [(local_ids[int(r)], float(s))
                     for s, r in zip(D[0], I[0]) if 0 <= int(r) < len(local_ids)]

            with pg.cursor() as cur:
                cur.execute(
                    "SELECT id, 1 - (embedding_v <=> %s::vector) "
                    "FROM rag_app_searchindex "
                    "WHERE source_type='chunk' AND embedding_v IS NOT NULL "
                    "ORDER BY embedding_v <=> %s::vector LIMIT %s",
                    [lit, lit, FETCH])
                remote = [(int(a), float(b)) for a, b in cur.fetchall()]

            ok, reasons = compare(local, remote)
            if not ok:
                failures += 1
            mark = 'PASS' if ok else 'FAIL'
            print(f"{mark}  {q[:58]}")
            if not ok:
                print(f"      local : {local[:TOP_K]}")
                print(f"      remote: {remote[:TOP_K]}")
                for why in reasons:
                    print(f"      reason: {why}")

    print()
    if failures:
        print(f"FAIL  {failures}/{len(QUERIES)} queries diverged - DO NOT cut over")
        return 1
    print(f"PASS  {len(QUERIES)}/{len(QUERIES)} queries: top-{TOP_K} coverage, "
          f"scores within {TOL}, order matches outside verified ties")
    return 0


if __name__ == '__main__':
    sys.exit(main())
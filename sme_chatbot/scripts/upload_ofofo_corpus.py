#!/usr/bin/env python3
"""Copy shared Ofofo collections from local Milvus Lite onto Zilliz.

Does not touch existing kb_* tenant collections.
Reuses stored embeddings (no re-encode).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

LOCAL_DB = Path("/Users/kali_ops/Downloads/ofofo_AI/milestone_two/db/ofofo_vectors.db")
COLLECTIONS = ("nairaland_discourse", "nigerian_replies", "nigerian_slang")
BATCH = int(os.getenv("UPLOAD_BATCH", "80"))
# 0 = no cap (upload until local data or Zilliz quota is exhausted).
CAP = int(os.getenv("UPLOAD_CAP_PER_COLLECTION", "0"))
FIELDS = ["id", "embedding", "text", "source", "section", "date", "author", "metadata_json"]


def _clip(row: dict) -> dict:
    return {
        "embedding": row["embedding"],
        "text": (row.get("text") or "")[:8192],
        "source": (row.get("source") or "")[:256],
        "section": (row.get("section") or "")[:128],
        "date": (row.get("date") or "")[:64],
        "author": (row.get("author") or "")[:256],
        "metadata_json": (row.get("metadata_json") or "{}")[:4096],
    }


def _ensure_collection(client: MilvusClient, name: str) -> None:
    if name in client.list_collections():
        return
    fields = [
        FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=384),
        FieldSchema("text", DataType.VARCHAR, max_length=8192),
        FieldSchema("source", DataType.VARCHAR, max_length=256),
        FieldSchema("section", DataType.VARCHAR, max_length=128),
        FieldSchema("date", DataType.VARCHAR, max_length=64),
        FieldSchema("author", DataType.VARCHAR, max_length=256),
        FieldSchema("metadata_json", DataType.VARCHAR, max_length=4096),
    ]
    schema = CollectionSchema(fields=fields, enable_dynamic_field=True)
    index_params = client.prepare_index_params()
    index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(collection_name=name, schema=schema, index_params=index_params)
    print(f"  created {name} on Zilliz", flush=True)


def _page(local: MilvusClient, name: str, last_id: int, limit: int) -> list[dict]:
    return local.query(
        collection_name=name,
        filter=f"id > {last_id}",
        output_fields=FIELDS,
        limit=limit,
    )


def _skip_already(local: MilvusClient, name: str, already: int) -> int:
    """Advance past local rows already copied (approx: first `already` ids)."""
    last_id = 0
    seen = 0
    while seen < already:
        rows = _page(local, name, last_id, min(BATCH * 4, already - seen))
        if not rows:
            break
        last_id = max(int(r["id"]) for r in rows)
        seen += len(rows)
    print(f"  {name}: resumed after ~{seen:,} local rows (last_id={last_id})", flush=True)
    return last_id


def upload_one(local: MilvusClient, remote: MilvusClient, name: str) -> int:
    _ensure_collection(remote, name)
    already = int(remote.get_collection_stats(name).get("row_count") or 0)
    target = CAP if CAP > 0 else 10**12
    if already >= target:
        print(f"  {name}: already {already:,} (>= cap {CAP:,}) — skip", flush=True)
        return already

    last_id = _skip_already(local, name, already) if already else 0
    inserted = already
    t0 = time.time()
    while inserted < target:
        try:
            rows = _page(local, name, last_id, BATCH)
        except Exception as exc:
            print(f"  {name}: local query failed after id={last_id}: {exc}", flush=True)
            time.sleep(2)
            continue
        if not rows:
            break
        last_id = max(int(r["id"]) for r in rows)
        payload = [_clip(r) for r in rows]
        for attempt in range(5):
            try:
                remote.insert(collection_name=name, data=payload)
                break
            except Exception as exc:
                wait = 2 ** attempt
                print(f"  {name}: insert retry {attempt+1} after {wait}s: {exc}", flush=True)
                time.sleep(wait)
        else:
            print(f"  {name}: giving up at id={last_id}", flush=True)
            break
        inserted += len(payload)
        if inserted % 800 < BATCH:
            rate = (inserted - already) / max(1, time.time() - t0)
            label = f"{CAP:,}" if CAP else "all"
            print(f"  {name}: {inserted:,}/{label}  ({rate:.1f} rows/s)", flush=True)
    print(f"  {name}: done {inserted:,} rows", flush=True)
    return inserted


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.config import get_settings

    s = get_settings()
    if not s.milvus_uri:
        print("MILVUS_URI is empty", file=sys.stderr)
        return 2

    print(f"local={LOCAL_DB}", flush=True)
    print(f"cap={CAP:,} batch={BATCH} collections={list(COLLECTIONS)}", flush=True)
    local = MilvusClient(str(LOCAL_DB))
    remote = MilvusClient(uri=s.milvus_uri, token=s.milvus_token)
    print("zilliz before:", remote.list_collections(), flush=True)

    totals = {}
    for name in COLLECTIONS:
        print(f"\n== {name} ==", flush=True)
        totals[name] = upload_one(local, remote, name)

    print("\nzilliz after:")
    for n in remote.list_collections():
        print(f"  {n}: {remote.get_collection_stats(n).get('row_count')}")
    print("uploaded", totals)
    local.close()
    remote.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

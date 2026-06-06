"""Analytics endpoints for the admin dashboard.

These compute aggregate metrics directly from the `turns` + `audit_records`
tables. For pilot-stage traffic (<10K turns/day per tenant) the queries are
fast enough without a materialised view; that's a Sprint 5 optimisation
when traffic justifies it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..db import pool as get_pool

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tenants", tags=["analytics"])


_WINDOWS = {"24h": timedelta(hours=24),
            "7d":  timedelta(days=7),
            "30d": timedelta(days=30)}


def _since(window: str) -> datetime:
    if window not in _WINDOWS:
        raise HTTPException(status_code=400, detail=f"window must be one of {list(_WINDOWS)}")
    return datetime.now(timezone.utc) - _WINDOWS[window]


@router.get("/{tenant_id}/analytics/summary")
def get_summary(tenant_id: str, window: str = Query(default="7d")):
    since = _since(window)
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            # Headline counts
            cur.execute(
                """
                SELECT
                    COUNT(*)                                                   AS messages_total,
                    COUNT(*) FILTER (WHERE role = 'user')                      AS user_msgs,
                    COUNT(*) FILTER (WHERE escalated)                          AS escalations,
                    AVG(CASE WHEN role = 'assistant' THEN 1 END)               AS dummy_avg
                FROM turns
                WHERE tenant_id = %s AND received_at >= %s
                """,
                (tenant_id, since),
            )
            row = cur.fetchone() or (0, 0, 0, None)
            total, user_msgs, escalations, _ = row

            # Language mix
            cur.execute(
                """
                SELECT detected_language, COUNT(*)
                FROM turns
                WHERE tenant_id = %s AND received_at >= %s
                    AND role = 'user' AND detected_language IS NOT NULL
                GROUP BY detected_language
                """,
                (tenant_id, since),
            )
            by_language = {r[0]: r[1] for r in cur.fetchall()}

            # Latency percentiles from audit records
            cur.execute(
                """
                SELECT
                    percentile_cont(0.5)  WITHIN GROUP (ORDER BY (latency_breakdown_ms->>'total_ms')::float) AS p50,
                    percentile_cont(0.95) WITHIN GROUP (ORDER BY (latency_breakdown_ms->>'total_ms')::float) AS p95,
                    percentile_cont(0.99) WITHIN GROUP (ORDER BY (latency_breakdown_ms->>'total_ms')::float) AS p99
                FROM audit_records
                WHERE tenant_id = %s AND created_at >= %s
                """,
                (tenant_id, since),
            )
            lat = cur.fetchone() or (None, None, None)

    except Exception as exc:                              # pragma: no cover
        log.exception("analytics summary failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    deflection = 1 - (escalations / user_msgs) if user_msgs else 0.0
    return {
        "tenant_id": tenant_id,
        "window": window,
        "messages_total": int(total or 0),
        "user_messages": int(user_msgs or 0),
        "escalations_total": int(escalations or 0),
        "deflection_rate": round(deflection, 3),
        "avg_latency_p50_ms": int(lat[0]) if lat and lat[0] else 0,
        "avg_latency_p95_ms": int(lat[1]) if lat and lat[1] else 0,
        "avg_latency_p99_ms": int(lat[2]) if lat and lat[2] else 0,
        "by_language": by_language,
    }


@router.get("/{tenant_id}/analytics/timeseries")
def get_timeseries(
    tenant_id: str,
    metric: str = Query(default="messages"),
    window: str = Query(default="7d"),
):
    since = _since(window)
    if metric not in {"messages", "escalations"}:
        raise HTTPException(status_code=400, detail="metric must be 'messages' or 'escalations'")

    where_extra = " AND escalated" if metric == "escalations" else ""

    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT date_trunc('hour', received_at) AS bucket, COUNT(*)
                FROM turns
                WHERE tenant_id = %s AND received_at >= %s{where_extra}
                GROUP BY 1
                ORDER BY 1
                """,
                (tenant_id, since),
            )
            rows: list[tuple[Any, Any]] = cur.fetchall()
    except Exception as exc:                              # pragma: no cover
        log.exception("analytics timeseries failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "tenant_id": tenant_id,
        "metric": metric,
        "window": window,
        "points": [{"t": r[0].isoformat() if r[0] else None, "v": int(r[1])} for r in rows],
    }

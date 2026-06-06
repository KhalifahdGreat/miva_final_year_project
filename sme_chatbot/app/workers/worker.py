"""Worker entry point.

    python -m app.workers.worker

Picks up both `whatsapp` and `ingestion` queues by default. In production we
typically run two separate worker dynos — one per queue — so a slow
ingestion never blocks WhatsApp message delivery.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from rq import Worker

from ..config import get_settings
from .queues import ingestion_queue, redis_conn, whatsapp_queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queues",
        nargs="+",
        default=["whatsapp", "ingestion"],
        help="Which queues this worker should listen on.",
    )
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=settings.app_log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )
    log = logging.getLogger("worker")

    available = {"whatsapp": whatsapp_queue(), "ingestion": ingestion_queue()}
    queues = [available[q] for q in args.queues if q in available]
    if not queues:
        log.error("no valid queues selected: %s", args.queues)
        return 2

    log.info("starting RQ worker on queues=%s redis=%s",
             [q.name for q in queues], settings.redis_url)
    Worker(queues, connection=redis_conn(), name=os.environ.get("DYNO", "worker")).work(
        with_scheduler=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

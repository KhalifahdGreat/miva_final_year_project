"""Background workers (RQ-based).

Two queues are operated:

    * `whatsapp`     — handles inbound WhatsApp webhook events. The HTTP
                       webhook handler enqueues raw payloads and ACKs Meta
                       within milliseconds; the worker does the orchestration
                       work asynchronously.
    * `ingestion`    — handles document chunking + embedding + upsert when the
                       upload is too large to finish during a single request
                       (Sprint 3 will route uploads through here unconditionally).

Workers are started by `python -m app.workers.worker`.
"""

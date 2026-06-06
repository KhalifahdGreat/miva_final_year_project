# Channels and Public API

This document specifies the **edge layer** — how messages get into and out of the platform, and how the admin dashboard talks to the backend.

It covers:

- WhatsApp Business Cloud API integration.
- The embeddable web widget.
- The public REST API (used by the dashboard, the widget, and pilot integrations).
- Authentication, idempotency, and retry semantics.

---

## Table of Contents

1. [Channel Adapter Interface](#1-channel-adapter-interface)
2. [WhatsApp Business Cloud API](#2-whatsapp-business-cloud-api)
3. [Web Widget](#3-web-widget)
4. [Public REST API](#4-public-rest-api)
5. [Authentication and Authorisation](#5-authentication-and-authorisation)
6. [Idempotency and Retries](#6-idempotency-and-retries)
7. [Error Model](#7-error-model)
8. [Rate Limiting](#8-rate-limiting)
9. [(Future) Instagram and Messenger](#9-future-instagram-and-messenger)

---

## 1. Channel Adapter Interface

Every channel implements the same `ChannelAdapter` Protocol (defined in `01_ARCHITECTURE.md` §3.8). The adapter has four responsibilities:

1. **Verify** the inbound webhook (signature / origin).
2. **Parse** the channel-specific payload into one or more `CanonicalMessage`s.
3. **Send** an outbound text reply.
4. **Send** auxiliary signals (typing indicator, read receipts) where the channel supports them.

The adapter does **not**:

- Touch the database.
- Make business decisions about whether to reply.
- Format the reply text (the orchestrator already returns final text).

```python
class ChannelAdapter(Protocol):
    name: str

    def verify_webhook(self, headers: dict, raw_body: bytes) -> bool: ...
    def parse_inbound(self, raw_payload: dict) -> list[CanonicalMessage]: ...
    def send_reply(self, msg: CanonicalMessage, reply_text: str) -> None: ...
    def send_typing_indicator(self, msg: CanonicalMessage) -> None: ...
```

---

## 2. WhatsApp Business Cloud API

The primary channel. Spec is the **Meta Cloud API** (https://developers.facebook.com/docs/whatsapp/cloud-api).

### 2.1 Onboarding flow (per tenant)

1. Tenant clicks "Connect WhatsApp" in the dashboard.
2. They are redirected through **Meta Embedded Signup** (Tech Provider flow). They sign in with Facebook, accept the WhatsApp Business Account terms, pick or create a phone number, and verify it via SMS / voice.
3. Meta returns a callback with `phone_number_id`, `waba_id`, and a system user access token.
4. We persist these in `tenant_whatsapp_credentials` (encrypted at rest).
5. We register our webhook URL with Meta for that WABA.
6. Tenant's bot is now reachable from any WhatsApp account.

For the thesis pilot, **a shared Tech Provider account** can host all SME numbers — the embedded signup is simplified and the token store is centralised.

### 2.2 Webhook receiver

```
POST  /webhooks/whatsapp
GET   /webhooks/whatsapp        (Meta verification challenge)
```

GET handler:

```
GET /webhooks/whatsapp?hub.mode=subscribe&hub.challenge=12345&hub.verify_token=<our_token>
→  200 OK with the value of hub.challenge
```

POST handler — verifies `X-Hub-Signature-256` then dispatches each entry:

```jsonc
// Inbound payload (text message), trimmed
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<waba_id>",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "+2348012345678",
          "phone_number_id": "1234567890"
        },
        "contacts": [{"profile": {"name": "Aminat"}, "wa_id": "2348011112222"}],
        "messages": [{
          "from": "2348011112222",
          "id": "wamid.HBgN...",
          "timestamp": "1737000000",
          "text": {"body": "Bros, e still get the gold watch?"},
          "type": "text"
        }]
      },
      "field": "messages"
    }]
  }]
}
```

The adapter's `parse_inbound`:

```python
def parse_inbound(self, raw: dict) -> list[CanonicalMessage]:
    out = []
    for entry in raw.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            tenant_id = self._tenants.tenant_for_phone_number_id(phone_number_id)
            for m in value.get("messages", []) or []:
                if m.get("type") != "text":
                    continue
                out.append(CanonicalMessage(
                    tenant_id=tenant_id,
                    channel="whatsapp",
                    sender_id=m["from"],
                    text=m["text"]["body"],
                    attachments=[],
                    received_at=datetime.fromtimestamp(int(m["timestamp"]), tz=timezone.utc),
                    channel_msg_id=m["id"],
                ))
    return out
```

### 2.3 Sending a reply

```python
def send_reply(self, msg, reply_text):
    creds = self._tenants.creds_for(msg.tenant_id)
    url = f"https://graph.facebook.com/v20.0/{creds.phone_number_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": msg.sender_id,
        "type": "text",
        "text": {"body": reply_text[:4096]}
    }
    requests.post(url, headers={"Authorization": f"Bearer {creds.access_token}"},
                  json=body, timeout=8.0)
```

### 2.4 Supported message types

| Type | Inbound | Outbound | Notes |
|---|---|---|---|
| `text` | ✓ | ✓ | Primary. |
| `image` | ✓ (acknowledge content; do not run OCR in v1) | ✗ | Future work. |
| `audio` (voice note) | ✗ MVP scope | ✗ | Out of scope per `00 §4.2`. |
| `location` | ✓ (acknowledge) | ✗ | Useful for delivery questions; respond textually. |
| `interactive` (buttons) | – | ✓ | For "Talk to a person" style escalation. |
| `template` | – | ✓ (optional) | Required for proactive messages outside the 24h customer-care window. |

### 2.5 The 24-hour rule

WhatsApp restricts business-initiated messages to a **24-hour customer service window** following the customer's last inbound. Outside that window, only pre-approved **template messages** can be sent. The orchestrator does not initiate; it only replies. So the rule mainly matters for handoff notifications, which go to the SME owner via the SME's own channel (email or a separate WhatsApp template), not back to the customer.

### 2.6 Delivery receipts (status callbacks)

Meta posts `sent`, `delivered`, `read` status events to the same webhook. We store these against `turn.outbound_status` to compute *deflection* metrics (a customer who reads a bot reply and stops messaging is a successfully deflected case).

---

## 3. Web Widget

A first-party widget. Single `<script>` tag installs it; supports text chat with typing indicator and read receipts. Themable to the SME's brand colour.

### 3.1 Install snippet

```html
<!-- Tenant copies this from the dashboard's Settings → Web Widget section -->
<script
  src="https://widget.<your-domain>.com/v1/widget.js"
  data-tenant-id="3a9f...c2"
  data-widget-key="pk_live_..."
  data-color="#0f766e"
  defer></script>
```

The script:

1. Creates an iframe pinned to the bottom-right corner.
2. Loads the chat UI from `https://widget.<your-domain>.com/v1/chat.html?tenant=...`.
3. Establishes a session via `POST /widget/v1/session` and receives a `session_token`.
4. Sends/receives messages over `POST /widget/v1/message` (long-poll for v1; WebSocket optional in v2).

### 3.2 Session model

A widget session is an ephemeral `(tenant_id, session_id)` pair, with a 24-hour TTL. The `session_id` doubles as the orchestrator's `sender_id` (a UUID). No PII is required from the visitor.

### 3.3 Endpoints

```
POST /widget/v1/session
  Headers:   Origin: <tenant.allowed_origin>
  Body:      {"widget_key": "pk_live_..."}
  Response:  {"session_token": "...", "greeting": "<config.greeting>"}

POST /widget/v1/message
  Headers:   Authorization: Bearer <session_token>
  Body:      {"text": "...", "attachments": []}
  Response:  {"reply": "...", "escalated": false, "turn_id": "..."}

POST /widget/v1/feedback
  Headers:   Authorization: Bearer <session_token>
  Body:      {"turn_id": "...", "rating": "up" | "down", "note": "..."}
  Response:  {"ok": true}
```

### 3.4 Origin pinning

Each tenant's widget key is bound to a list of allowed origins (set in dashboard). Cross-origin requests with an unauthorised origin → 403.

### 3.5 Visual contract (out of scope for engineering, but record for the thesis)

- Avatar: tenant's logo (uploaded in dashboard) or a default mark.
- Bubble alignment: left for bot, right for visitor.
- Fonts: `system-ui, -apple-system, "Segoe UI"` — no web font fetch (size, performance).
- Bundle target: ≤ 30 KB gzipped.

---

## 4. Public REST API

All admin / pilot integrations use this. Versioned at `/v1`.

### 4.1 Conventions

- All requests use `Content-Type: application/json`.
- All responses include a top-level `request_id` echoed in `X-Request-Id`.
- Times are ISO-8601 UTC.
- Errors follow §7.

### 4.2 Auth endpoints

(Authentication is delegated to Clerk / Auth.js — these are the platform-side endpoints.)

```
POST /v1/auth/exchange       Exchange Clerk JWT for a platform JWT
GET  /v1/auth/me             Current user, tenants they belong to
```

### 4.3 Tenant endpoints

```
GET    /v1/tenants/me                          Current tenant context
POST   /v1/tenants                             Create tenant (during onboarding)
PATCH  /v1/tenants/{tenant_id}                 Update tenant profile
GET    /v1/tenants/{tenant_id}/config          Get latest config
PUT    /v1/tenants/{tenant_id}/config          Save new config (creates revision)
GET    /v1/tenants/{tenant_id}/config/history  List revisions
POST   /v1/tenants/{tenant_id}/config/rollback {"version": 7}
```

### 4.4 Knowledge endpoints

```
POST   /v1/tenants/{tenant_id}/documents
  Body: multipart/form-data (file, document_type)
  201: {"document_id": "...", "status": "ingesting"}

GET    /v1/tenants/{tenant_id}/documents
GET    /v1/tenants/{tenant_id}/documents/{document_id}
DELETE /v1/tenants/{tenant_id}/documents/{document_id}

GET    /v1/tenants/{tenant_id}/chunks
       Query: document_id, q (semantic search), limit, offset
PATCH  /v1/tenants/{tenant_id}/chunks/{chunk_id}
  Body: {"text": "...", "boost": 1.5}
DELETE /v1/tenants/{tenant_id}/chunks/{chunk_id}

POST   /v1/tenants/{tenant_id}/manual-faq
  Body: {"question": "...", "answer": "...", "language_hint": "pid"}
```

### 4.5 Conversation endpoints

```
GET  /v1/tenants/{tenant_id}/conversations
     Query: language, escalated, from, to, limit, cursor
GET  /v1/tenants/{tenant_id}/conversations/{conversation_id}
GET  /v1/tenants/{tenant_id}/conversations/{conversation_id}/turns
POST /v1/tenants/{tenant_id}/conversations/{conversation_id}/feedback
     Body: {"turn_id": "...", "rating": "up"|"down",
            "corrected_answer": "...", "note": "..."}
```

### 4.6 Analytics endpoints

```
GET  /v1/tenants/{tenant_id}/analytics/summary
     Query: window=7d|30d
     Response: {
       "messages_total": 1432,
       "deflection_rate": 0.81,
       "escalations_total": 27,
       "avg_latency_p50_ms": 2400,
       "avg_latency_p95_ms": 5800,
       "by_language": {"en": 0.55, "pid": 0.40, "yo": 0.05},
       "top_intents": [...]
     }

GET  /v1/tenants/{tenant_id}/analytics/timeseries
     Query: metric=messages|deflection|latency, window=7d|30d, granularity=hour|day
```

### 4.7 Channel endpoints

```
POST /v1/tenants/{tenant_id}/channels/whatsapp/connect
     Body: {"phone_number_id": "...", "waba_id": "...", "access_token": "..."}
GET  /v1/tenants/{tenant_id}/channels/whatsapp/status
DELETE /v1/tenants/{tenant_id}/channels/whatsapp

POST /v1/tenants/{tenant_id}/channels/widget/regenerate-key
GET  /v1/tenants/{tenant_id}/channels/widget/snippet
```

### 4.8 Webhook endpoints (inbound from channels)

```
GET  /webhooks/whatsapp        Meta verification challenge
POST /webhooks/whatsapp        Inbound messages and statuses
```

---

## 5. Authentication and Authorisation

### 5.1 Tokens

| Audience | Mechanism |
|---|---|
| Dashboard users | Clerk-issued OAuth (Google) → exchanged for platform JWT |
| Pilot integrations | Long-lived API key (`Bearer sk_live_...`) scoped to a tenant |
| Web widget | Short-lived `session_token` issued per visitor session |
| Channel webhooks (Meta) | `X-Hub-Signature-256` validated against Meta app secret |

### 5.2 Tenant scoping

Every authenticated request resolves to a `(user_id, tenant_id, role)` triple. The tenant_id is **always** taken from the authenticated context — never from a path parameter alone. The path parameter exists for clarity in URLs but the server discards it if it disagrees with the authenticated tenant.

### 5.3 Roles (MVP)

- `owner` — full control, billing (when added), tenant lifecycle.
- `staff` — knowledge, conversations, persona, but not tenant-level destructive ops.

(Granular RBAC is explicitly out of scope per `00 §4.2`.)

---

## 6. Idempotency and Retries

### 6.1 Inbound webhooks

- **WhatsApp.** Meta retries failed deliveries up to **7 times over 24h**. Idempotency key: `channel_msg_id`. The orchestrator first checks `processed_messages` (a small Postgres table with a unique index on `(tenant_id, channel_msg_id)`); if present, it ACKs without reprocessing.
- **Widget.** No duplicate retries — the client is in the same session and gets back the response synchronously.

### 6.2 Outbound LM calls

- Retried inside `LMClient.complete` up to 3 times on transient errors (see `02_CORE_ENGINE.md` §2). The orchestrator does **not** retry around the LM call — that would compound retries and skew latency.

### 6.3 Outbound channel sends

- Retried up to 2 times on transient failures from Meta (5xx). On final failure, the turn is marked `outbound_failed=true` and the SME owner is notified through the dashboard's alerts panel.

### 6.4 Webhook ACK semantics

- Always ACK Meta with **200 OK** as soon as the message is parsed and queued. Internal processing happens after the ACK. This protects Meta's queue from blocking.

---

## 7. Error Model

A standard error envelope:

```jsonc
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Document not found.",
    "details": {"document_id": "..."},
    "request_id": "req_..."
  }
}
```

### 7.1 Codes

| HTTP | Code | When |
|---|---|---|
| 400 | `INVALID_REQUEST` | Malformed body / missing field |
| 401 | `UNAUTHENTICATED` | No / invalid token |
| 403 | `FORBIDDEN` | Authenticated but wrong tenant |
| 404 | `RESOURCE_NOT_FOUND` | – |
| 409 | `CONFLICT` | Versioned save with stale `version` |
| 413 | `PAYLOAD_TOO_LARGE` | Upload > 25 MB |
| 422 | `VALIDATION_ERROR` | Pydantic validation failed |
| 429 | `RATE_LIMITED` | – |
| 500 | `INTERNAL_ERROR` | Unhandled |
| 502 | `UPSTREAM_ERROR` | LM provider returned 5xx after retries |
| 503 | `SERVICE_UNAVAILABLE` | DB / vector down |

### 7.2 Surfaced behaviour

- `LM_DOWN` → user-facing fallback text (configured per tenant) and an internal alert.
- `KB_DOWN` → user-facing "we're checking on that" + escalate.

---

## 8. Rate Limiting

Per-tenant token-bucket on a few axes:

| Axis | Default |
|---|---|
| Messages / minute (per tenant) | 120 |
| Document uploads / hour (per tenant) | 30 |
| Config saves / minute (per tenant) | 10 |
| Total LM tokens / day (per tenant) | 200,000 |

Violations return 429 with `Retry-After`.

---

## 9. (Future) Instagram and Messenger

Both share the Meta Graph API stack with WhatsApp. Adding them later is mostly a new adapter (`InstagramAdapter` / `MessengerAdapter`) that:

1. Resolves `tenant_id` from the page-id / IG-user-id.
2. Maps DM payload into `CanonicalMessage`.
3. Sends replies via the same Graph API.

The orchestrator and engine stay untouched. This is recorded as Future Work in the thesis (see `00 §4.2`).

# Setup Today — One Sitting, In Order

This guide walks you through every account, key and click needed to go from
"code on my laptop" to "live system reachable from the internet" in a single
afternoon. Follow it **top to bottom, one item at a time.** After each item
there's an explicit **"send me"** line — copy those values back into our chat
and I'll wire them up.

If you only do **Part 1** today (≈ 30 minutes), you'll have the full system
running locally and visible at `http://localhost:8000`. Parts 2 and 3 are
about pushing it to the internet — Meta's WhatsApp side is the only thing
that genuinely takes more than one sitting.

---

## Quick map: who needs an account, who runs on Docker

| Item                  | Needs account? | Docker locally?      | Time |
|-----------------------|----------------|----------------------|------|
| Postgres              | No             | **Yes (provided)**   | 2 min |
| Redis                 | No             | **Yes (provided)**   | 2 min |
| Groq (LLM)            | **Yes**        | No (hosted only)     | 5 min |
| GitHub                | **Yes**        | No                   | 5 min |
| Cloudflare R2         | **Yes**        | Yes via MinIO, but R2's easier | 15 min |
| Render (backend host) | **Yes**        | No                   | 20 min |
| Vercel (dashboard)    | **Yes**        | No                   | 10 min |
| Clerk (auth)          | **Yes**        | No                   | 10 min |
| Meta WhatsApp         | **Yes**        | No (only Meta runs the API) | 30 min today + 1–14 days approval |

The Postgres + Redis containers are already wired up in `docker-compose.yml`,
so today you don't need to use Render's managed Postgres/Redis at all. Render
comes back into the picture in **Part 2** for hosting the backend itself.

---

# PART 1 — Get it running on your laptop (30 minutes)

## 1.  Make sure Docker is up

You already have Docker — I just verified it. Bring up the project's
Postgres + Redis containers:

```bash
cd /Users/kali_ops/Downloads/ofofo_AI/final_year_project/sme_chatbot
docker compose up -d
docker compose ps
```

You should see `sme-chatbot-postgres` and `sme-chatbot-redis` both `Up (healthy)`.
The ports are deliberately **5433** and **6380** so they don't fight with your
`shae-brain-*` containers that are already using 5432 and 6379.

**Nothing to send me here** — this is local-only.

## 2.  Apply the database schema

```bash
docker exec -i sme-chatbot-postgres \
    psql -U postgres -d sme_chatbot < migrations/001_initial.sql
```

This creates the 13 tables we need. You should see a wall of `CREATE TABLE` /
`CREATE INDEX` lines, no errors.

**Nothing to send me.**

## 3.  Get a Groq API key (5 minutes)

This is the only LLM provider in the project — there's no Docker
alternative because we're using Llama 3.3 70B and you'd need an H100
to run it yourself.

1. Open <https://console.groq.com> in your browser.
2. Sign up (Google login is fastest).
3. In the left sidebar, click **API Keys**.
4. Click **Create API Key** → name it `sme-chatbot-fyp` → **Submit**.
5. Copy the key — it starts with `gsk_…`.

**Send me:** the Groq key (or paste it into `.env` directly under
`GROQ_API_KEY=`).

You already have one from the parent project; if you want to reuse it
that's fine.

## 4.  Verify the whole stack runs locally

In one terminal:

```bash
cd /Users/kali_ops/Downloads/ofofo_AI/final_year_project/sme_chatbot
make smoke-persist
```

Expected output (last few lines):

```
[5/5] Verifying analytics summary aggregation ...
      messages_total    : 2
      escalations_total : 0
      deflection_rate   : 1.0
      by_language       : {'pid': 1}

All checks passed. Persistence + audit + analytics work end-to-end.
```

If you see that, **the entire backend works on your machine right now**.
A real Pidgin question went through the Groq Llama 3.3 70B model, used
your local Postgres for history, and wrote an audit record.

In a second terminal, start the FastAPI server in dev mode:

```bash
make dev
```

Open <http://localhost:8000/docs> in your browser. You'll see the full
OpenAPI documentation with every endpoint. That is the system.

**Nothing to send me.** You're done with Part 1.

---

# PART 2 — Push it onto the internet (90 minutes)

## 5.  GitHub repo (5 minutes)

Render and Vercel both pull code from GitHub. We need a remote.

1. Open <https://github.com/new> in your browser.
2. Repository name: `sme-chatbot` (or whatever you prefer).
3. Set it to **Private**.
4. **Don't** initialise with a README or .gitignore — we have our own.
5. Click **Create repository**.
6. On the next page, copy the URL — it's either
   `git@github.com:<your-username>/sme-chatbot.git` (SSH) or
   `https://github.com/<your-username>/sme-chatbot.git` (HTTPS).

**Send me:** the repo URL. I'll initialise the local git repo, configure
.gitignore so secrets are never committed, and push the first version.

> **Privacy note:** the parent `ofofo_AI/` folder will NOT be pushed.
> We push only `final_year_project/sme_chatbot/` so the thesis project
> lives independently in its own repo.

## 6.  Cloudflare R2 bucket (15 minutes)

This holds the original PDFs/DOCX files SMEs upload. The Milvus vectors
are derived from them; R2 is where the source-of-truth files live so
the SME can re-download them later.

1. Open <https://dash.cloudflare.com> and sign up (free).
2. In the left sidebar, click **R2**. The first time you click it,
   Cloudflare will ask you to add a payment card to "activate" R2 —
   this is anti-abuse only; nothing is charged unless you exceed 10 GB
   of storage. **Skip this step if you want** and use MinIO in Docker
   instead — I'll add that container if you tell me to.
3. Click **Create bucket** → name it `sme-chatbot-uploads` → location
   `Automatic` → **Create**.
4. Click **Manage R2 API tokens** in the right sidebar.
5. Click **Create API token** → name `sme-chatbot-prod`.
   * **Permissions:** **Object Read & Write**.
   * **Specify bucket:** select your bucket.
   * **TTL:** Forever.
   * Click **Create API Token**.
6. On the success page, copy:
   * **Access Key ID**
   * **Secret Access Key**
   * **Use jurisdiction-specific endpoints for S3 clients** → the URL
     under "Default" — it looks like
     `https://<random>.r2.cloudflarestorage.com`.

**Send me:** all three values. I'll fill them into the `.env` and into
Render's secret store.

> **Don't want to deal with R2?** Tell me and I'll add MinIO to
> `docker-compose.yml`. It's a free, S3-compatible Docker container.
> For a pilot of 3-4 SMEs it would actually be fine. Cost: zero
> external accounts.

## 7.  Render account + deploy the backend (20 minutes)

This is what gives WhatsApp a public URL to talk to. The free tier
sleeps after 15 min of inactivity, which is fine for a pilot — the
"Starter" tier is $7/month if you want to skip the cold starts.

1. Open <https://render.com> and sign up with your GitHub account
   (this also lets Render see your `sme-chatbot` repo).
2. Click **New +** → **Blueprint** in the top-right.
3. Select your `sme-chatbot` repository.
4. Render will detect `render.yaml` and show you the two services it's
   about to create — **sme-chatbot-api** (web) and **sme-chatbot-worker**
   (background). Click **Apply**.
5. Before it can deploy, Render asks for the three secret values it
   couldn't infer:
   * `DATABASE_URL` — see step 7a below.
   * `REDIS_URL` — see step 7b below.
   * `GROQ_API_KEY` — paste the value from step 3.

### 7a.  Free managed Postgres on Render

In a separate browser tab:

1. Render dashboard → **New +** → **PostgreSQL**.
2. Name: `sme-chatbot-db`. Region: **Frankfurt** (closest to Nigeria
   on the free tier). Plan: **Free**.
3. **Create database**. Wait 60 seconds.
4. On the database page, scroll to **Connections** → copy the
   **External Database URL**. It starts with `postgresql://…`.
5. Paste it into the Render Blueprint's `DATABASE_URL` field.

### 7b.  Free managed Redis on Render

Same pattern:

1. Render dashboard → **New +** → **Redis**. Name: `sme-chatbot-redis`,
   Plan: **Free**. **Create**.
2. Copy the **Internal Redis URL** (starts with `redis://red-…`).
3. Paste it into the Blueprint's `REDIS_URL` field.

Click **Apply** at the bottom. Render will:

* build the Docker image (~5 min),
* spin up the web service,
* spin up the worker service,
* expose the web service at
  `https://sme-chatbot-api.onrender.com` (your URL will have your random
  service ID — copy it from the service page).

**Once it's live, send me:** the URL of the web service. I'll add it to
`WIDGET_ALLOWED_ORIGINS` and we'll test the deployed `/health` endpoint
together.

> **What you do NOT need to do here:** apply the migrations manually.
> The first time the worker boots, I'll have it auto-apply
> `migrations/001_initial.sql` (I'll add the migration step in the next
> deploy after we wire this up).

## 8.  Vercel for the dashboard + widget (10 minutes)

The Next.js dashboard you saw earlier needs a host that understands
Next.js — Vercel is built by the same team.

1. <https://vercel.com> → sign up with GitHub.
2. **Add New** → **Project** → import your `sme-chatbot` repo.
3. When Vercel asks **Root Directory**, click **Edit** and set it to
   `final_year_project/sme_chatbot/dashboard`.
4. **Framework Preset:** Next.js (auto-detected).
5. Under **Environment Variables**:
   * `NEXT_PUBLIC_API_BASE` = the Render URL from step 7
     (e.g. `https://sme-chatbot-api.onrender.com`).
6. Click **Deploy**.

In ~3 minutes the dashboard is live at something like
`https://sme-chatbot.vercel.app`.

**Send me:** the Vercel URL.

## 9.  Clerk for authentication (10 minutes)

So SME owners can sign in to their dashboard.

1. <https://clerk.com> → sign up with GitHub.
2. **Create application** → name it `sme-chatbot`.
3. Under **Configure** → **Email** + **Google** sign-in enabled
   (default). Click **Create application**.
4. On the **API Keys** page, copy:
   * **Publishable key** (starts with `pk_test_…`).
   * **Secret key** (starts with `sk_test_…`).

**Send me:** both keys. I'll wire Clerk into the Next.js dashboard +
add a middleware that injects the authenticated user's tenant into
every API call.

---

# PART 3 — WhatsApp (start today, finishes over 1-2 weeks)

## 10.  Meta Business + WhatsApp Cloud API

This is the slow one. Submitting the form takes 30 minutes today;
Meta then takes anywhere from **1 hour to 2 weeks** to verify your
"business" before the test number can send messages outside Meta's
internal preview. For a free-tier test number with 5 allowed
recipients, you can start sending TO yourself almost immediately —
that's enough to demo end-to-end before Meta finishes verification.

### 10a.  Create the Meta Business account

1. Go to <https://business.facebook.com>.
2. Click **Create account** in the top-right.
3. Form values:
   * **Business name:** something professional — e.g. "Onumoh Customer
     AI" or your future product name. Avoid joke names; Meta does
     review these.
   * **Your name + work email:** real ones.
4. Click **Submit**. You're now in Business Manager.

### 10b.  Create a Meta App with WhatsApp product

1. Go to <https://developers.facebook.com/apps>.
2. Click **Create app** in the top-right.
3. **Use case:** **Other** → **Continue**.
4. **App type:** **Business** → **Continue**.
5. **Add an app name:** `sme-chatbot`. **Contact email:** yours.
   **Business Account:** select the one you just made. **Create app**.
6. On the next page, find **WhatsApp** in the product list and
   click **Set up**.
7. Meta will auto-create a WhatsApp Business Account (WABA) and a
   test phone number. **This is the free, instant-approval number.**

### 10c.  Add YOUR own phone as a tester

1. Inside the WhatsApp panel → **API Setup**.
2. Scroll to **To** → click **Manage phone number list** → **Add
   recipient phone number**.
3. Enter your personal WhatsApp number (with `+234…`). Meta sends a
   6-digit code to your WhatsApp. Enter it.
4. You can now message yourself from the test number.

### 10d.  Collect the credentials and send me

From the same **API Setup** page:

* **App ID** — top of the page (e.g. `1234567890123456`).
* **App Secret** — go to **App Settings** → **Basic** in the left
  sidebar → click **Show** next to App Secret.
* **Phone Number ID** — listed in the API Setup table.
* **WhatsApp Business Account ID (WABA ID)** — same table.
* **Temporary access token** — listed in the API Setup table. **It
  expires in 24 hours**, so once you send it we should immediately
  generate a permanent one (instructions when we get there).

Also **make up a verify token** — any random string at least 16
characters long, e.g. open Python and run `python -c "import secrets; print(secrets.token_urlsafe(24))"`. This is what we'll tell Meta
when subscribing the webhook so Meta and our server can recognise each
other.

**Send me:** all six values (App ID, App Secret, Phone Number ID, WABA
ID, Temporary access token, Verify token you made up).

### 10e.  Subscribe the webhook (we do this together once Render is live)

This is the last step and we do it together because the order matters:

1. Render is live (step 7) ✓
2. Render env vars include `WHATSAPP_VERIFY_TOKEN` and
   `WHATSAPP_APP_SECRET` ✓
3. Then in the Meta WhatsApp panel → **Configuration** → **Webhook**:
   * **Callback URL:** `https://<your-render-url>/webhooks/whatsapp`.
   * **Verify token:** the one you made up in 10d.
   * Click **Verify and save** — Meta sends a GET to your URL with the
     verify token; if it matches, the subscription completes in
     <1 second.
4. Then subscribe to the **messages** webhook field.
5. Send yourself "hello" from any of the 5 allowed test numbers.
   Watch the worker logs on Render — the orchestrator should fire,
   call Groq, and a reply should arrive in your WhatsApp.

That's the demo moment.

---

# Tier 3 — People-and-marketing items (deferrable)

## 11.  Product name

Right now the dashboard says "SME Chatbot". For your defence and for
talking to pilot SMEs we need something with a bit of personality.
Three Nigerian-flavoured options I think work:

* **Yarn** — "as you yarn am" — short, memorable, Pidgin.
* **Sabi** — "to know how / be expert at" — implies the bot is
  knowledgeable.
* **Sokoto** — "speak / chat" in Yoruba; also a real city name, gives
  it geographic grounding.

Or propose your own. I'll rebrand the dashboard + widget header + the
README in 10 minutes once you pick.

## 12.  Elevator pitch (I'll draft, you sign off)

**v1 draft for SME owners:**

> "Your customers message your business on WhatsApp at all hours. You
> can't reply to every one of them yourself. **<Product>** is an
> AI-powered assistant that answers your customers' questions — in
> English, Pidgin, Yoruba, Hausa or Igbo — using your own catalogue,
> prices and FAQs. You upload your business documents once, connect
> your WhatsApp number, and the assistant handles the routine
> questions while flagging anything tricky for you to handle
> personally. Setup is ten minutes; the first month is free."

Tell me if that lands or if you want it tighter / more formal / more
Nigerian-pidgin in tone — I'll rewrite to your taste.

## 13.  Pilot SMEs

We can't sign these up until the rest of the system is on the
internet, but you can start sourcing now. We want **three to four**
businesses, ideally:

* One **food / fashion vendor** (Pidgin-heavy customer base).
* One **service business** — clinic / barber / consultancy (English-heavy).
* One **electronics / phone shop** (code-switched, asks lots of price
  questions — exercises the hallucination guard).

I'll write a one-paragraph pitch you can drop into WhatsApp /
Instagram DMs once we lock the product name. You bring names + numbers,
I'll handle technical onboarding.

---

# Checklist — copy this into our chat as you go

```
Part 1 — Local
[ ] 1. docker compose up -d                       (no input needed)
[ ] 2. Schema applied                              (no input needed)
[ ] 3. Groq API key                                → send me: gsk_xxxxx
[ ] 4. make smoke-persist passes                   (no input needed)

Part 2 — Internet
[ ] 5. GitHub repo created                         → send me: git URL
[ ] 6. Cloudflare R2 bucket + token                → send me: access key id,
                                                       secret access key,
                                                       S3 endpoint URL
[ ] 7. Render Blueprint deployed                    → send me: web service URL
[ ] 8. Vercel dashboard deployed                    → send me: vercel URL
[ ] 9. Clerk app created                            → send me: publishable key,
                                                       secret key

Part 3 — WhatsApp
[ ] 10. Meta app + WhatsApp number                  → send me: app id,
                                                       app secret,
                                                       phone_number_id,
                                                       WABA id,
                                                       temp access token,
                                                       verify token (you make up)

Tier 3 — Decisions
[ ] 11. Product name picked                         → send me: name
[ ] 12. Elevator pitch approved / edited            → reply with edits
[ ] 13. Pilot SME shortlist                         → send me: 3-4 names + numbers
```

---

# What I'll do as soon as you start sending values

The moment **any** value lands in chat, I'll plug it in immediately:

* **Groq key** → already-ready, just goes into `.env`.
* **GitHub URL** → I init the repo, push everything, configure CI.
* **R2 credentials** → I write the upload pipeline to use them and add
  a tiny round-trip test to the smoke suite.
* **Render URL** → I add it to `WIDGET_ALLOWED_ORIGINS`, point the
  dashboard's `NEXT_PUBLIC_API_BASE` at it, then we test the live
  `/health` together.
* **Clerk keys** → I add the Clerk middleware to the Next.js
  dashboard and protect every `/dashboard/*` route.
* **WhatsApp credentials** → I create your tenant row, insert the
  encrypted WhatsApp credentials, walk you through the Meta webhook
  subscription, and then we ping the production system together from
  your phone.

There's no batching — each item is a small, independent commit.
You don't have to do them in order strictly; the dependency map is:

```
Groq key                  -> needed everywhere
GitHub repo               -> needed before Render + Vercel
Render URL                -> needed before WhatsApp webhook
Clerk keys                -> needed before dashboard auth
WhatsApp creds            -> needed for the WhatsApp demo
R2 creds                  -> needed for document uploads in production
```

Everything else can happen in parallel.

Ping me with the first value whenever you're ready. I'm waiting.

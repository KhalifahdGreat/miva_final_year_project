# What I need from you

These are the **external accounts, credentials and people** I can't create
for you. Tackle them in roughly this order — the upper items are blockers
for the next sprint, the lower items are blockers for the pilot in
Sprint 4. Anything I can build without your input is being built in
parallel.

For every item below I have already written the code that will consume it.
You give me the values; I plug them into the `.env` and the live system
starts using them within minutes.

---

## TIER 1 — Needed in the next 2 weeks (blocks Sprint 2 finish)

### 1. Render account (free / starter tier is fine)

What it gives us: a live URL to point WhatsApp's webhook at, plus a
managed Postgres + Redis. Everything I'll deploy comes pre-configured in
`render.yaml`.

Steps:

1. Sign up at <https://render.com> with the email you want on the thesis.
2. In the Render dashboard, create:
   * **One Postgres instance** — free tier ("Hobby"). Copy the **External
     Database URL**.
   * **One Redis instance** — free tier. Copy the **Redis URL**.
3. Send me both URLs (paste into chat).
4. I'll commit a single `git push`, run `render blueprint apply`, and the
   web + worker services come up in about 5 minutes.

### 2. GROQ API key (free)

You already have one for the parent project. If you'd rather use a
separate one for the FYP so the usage stats are clean, create a second key:

1. Go to <https://console.groq.com/keys>.
2. Click **Create API Key**, name it `sme-chatbot-prod`.
3. Paste it in the chat (it starts with `gsk_…`).

### 3. Cloudflare R2 bucket (free, S3-compatible)

What it gives us: storage for the SME-uploaded documents (PDFs of price
lists, FAQs, policies). The Milvus vectors are derived; the original files
live in R2.

Steps:

1. Sign up at <https://dash.cloudflare.com>.
2. In the sidebar: **R2** -> **Create bucket**, name it `sme-chatbot-uploads`.
3. Under **Manage R2 API Tokens** -> **Create API token**:
   * Permissions: **Object Read & Write**, scoped to your one bucket.
   * Copy the **Access Key ID** and **Secret Access Key**.
   * Copy the **S3 endpoint URL** (looks like `https://<account>.r2.cloudflarestorage.com`).
4. Send me all three values.

### 4. Vercel account (free)

What it gives us: hosting for the Next.js admin dashboard and the
embeddable widget bundle.

1. Sign up at <https://vercel.com> with GitHub.
2. That's it — I'll wire the deploy in a later sprint.

### 5. A GitHub repo for the codebase

Right now everything lives on your laptop. We need a remote so Render +
Vercel can pull from it.

1. Create a private repo at <https://github.com> — name it `sme-chatbot`.
2. Tell me the repo URL.
3. I'll initialise git, push the project, and configure CI.

---

## TIER 2 — Needed in the next 4 weeks (blocks the live WhatsApp demo)

### 6. Meta Business Manager + WhatsApp Business Cloud API

This is the most involved item. Meta's onboarding is slow but the test
phone number is free.

Step-by-step:

1. **Create a Meta Business account.** Go to <https://business.facebook.com>,
   click **Create account**, follow the form. Use a real business name
   (you can use your own name + "FYP" — Meta accepts that for educational
   projects).

2. **Add a WhatsApp Business Account (WABA).** From Business Manager:
   * **Business Settings** -> **Accounts** -> **WhatsApp Accounts** -> **Add**.
   * Follow the prompts. You don't need a real business website for the
     test number — when asked, use the GitHub repo URL from item 5.

3. **Generate a Meta app.** Go to <https://developers.facebook.com/apps>:
   * **Create app** -> select **Business** -> name it `sme-chatbot`.
   * Once created, in the left sidebar: **Add Product** -> **WhatsApp**
     -> **Set up**.

4. **Get the test phone number.** Inside the WhatsApp panel of your app:
   * The first phone number is **free, instantly approved, and limited
     to 5 recipients** (which we add manually). For a pilot demo with 3-4
     SMEs this is sufficient.
   * Add YOUR personal WhatsApp number as one of the 5 allowed recipients
     so you can test.

5. **Collect the credentials.** From the WhatsApp panel send me:
   * **App ID** (top of the page).
   * **App Secret** (under **App Settings** -> **Basic** -> **Show**).
   * **Phone Number ID** (under WhatsApp -> API Setup).
   * **WhatsApp Business Account ID (WABA ID)** (same page).
   * A **temporary access token** (24-hour, generated in the panel) for
     initial smoke testing. We'll swap it for a permanent System User
     token before the pilot starts — I'll walk you through that when we
     get there.

6. **Pick a verify token.** This is any random string you make up — Meta
   sends it back to us during webhook subscription so we can recognise the
   call. Make one up (e.g. a random 30-character string) and send it to
   me. Treat it like a password.

7. **Wait until Render is up (item 1) before doing the webhook
   subscription** — Meta needs a public HTTPS URL to subscribe to, and
   Render gives us one (`https://sme-chatbot-api.onrender.com`). I'll
   show you the exact button to click in the Meta UI once Render is live.

---

## TIER 3 — Needed in 8 weeks (blocks the pilot)

### 8. Three to four pilot SMEs

The deliverable that earns the thesis marks. Ideal traits:

* Already have a WhatsApp Business number, OR are happy for customers to
  message the test number we got from Meta.
* Have at least one of: a product catalogue, an FAQ document, or a price
  list — anything we can ingest as the "knowledge base."
* Willing to let conversations be logged for evaluation (with their
  customers' informed consent — we'll provide the consent message they
  send to first-time customers).
* Diverse so the language coverage gets exercised: I'd target one
  Pidgin-heavy business (food vendor / fashion), one English-heavy
  (consultancy / clinic), and one code-switched (electronics / phones).

Send me names + WhatsApp numbers + a one-paragraph description of each.
I'll build a one-page onboarding form they can complete in 10 minutes
once we're ready.

### 9. A short business name and tagline for the platform itself

Right now the dashboard says "SME Chatbot." For your thesis demo it
should have a real product name — something Nigerian-flavoured but
professional. Examples to react to: "Yarn", "Talker", "Naija Concierge",
"Gist Desk". Pick one or propose your own and I'll rebrand the dashboard
+ widget in 10 minutes.

### 10. A 60-second elevator pitch (for the supervisor + the pilot SMEs)

A paragraph that explains what the system does in plain English, what
the SME gets out of using it, and what they (the SME) need to do. I'll
draft v1; you tell me if it sounds right for the audience.

---

## OPTIONAL but recommended

### 11. A `.com` or `.ng` domain (one-time ~$15 / year)

Render gives us `sme-chatbot-api.onrender.com` which is fine for the
thesis demo. A short custom domain (e.g. `sme-chatbot.ng`) looks more
credible to pilot SMEs. Namecheap is the cheapest. Optional.

### 12. Clerk account for the admin dashboard authentication

We'll need this to log SMEs in to their dashboards. Free tier covers
the whole pilot.

1. Sign up at <https://clerk.com> (GitHub login).
2. **Create application** -> name `sme-chatbot`.
3. Under **API Keys**, copy the **Publishable key** and the **Secret key**.
4. Send me both.

---

# What I am doing while you do those things

* **Now (today's work):**
  - [x] Postgres-backed conversation persistence
  - [x] Audit-record writes on every turn (the data your Chapter 5
        evaluation depends on)
  - [x] Real conversations + analytics + documents endpoints
  - [x] RQ background worker (so we respect Meta's 5-second SLA)
  - [x] Webhook idempotency (no double-replies)
  - [x] Production Dockerfile + render.yaml + Procfile
  - [x] Persistence smoke test

* **Next 2 weeks (in order):**
  - Clerk auth on the Next.js dashboard.
  - Real "review a conversation" UI showing every turn + retrieved
    chunks + the audit record.
  - Document-listing UI hooked up to `/v1/tenants/{tid}/documents`.
  - Onboarding wizard for tenants (create -> upload first doc ->
    connect WhatsApp -> test message).
  - Encrypted storage of the WhatsApp access token (instead of plain
    bytes — we'll use Fernet with a KMS-style master key in env).
  - Tenant-aware Postgres row-level security policies.

* **The week after:** wiring up YOUR tier-2 WhatsApp credentials to
  the live deploy, end-to-end test from your phone, then we hand
  pilot SMEs the dashboard URL.

---

# Decision points for YOU (not blocking, but better answered soon)

1. **Logo / brand colours?** Doesn't matter for the thesis but matters
   for the pilot SMEs reading your dashboard. If you don't care, I'll
   use Nigerian green (#16a34a) which is what's in the widget already.

2. **Pilot duration?** I've been writing "four weeks" in the thesis.
   Confirm that fits your defence calendar.

3. **Do you want analytics events sent to Langfuse?** Free tier, gives
   us a beautiful per-prompt trace view that's lovely to drop into
   Chapter 5. Default ON. Tell me to turn it OFF if you'd rather not
   sign up for one more account.

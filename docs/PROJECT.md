# Terminal-Hire — Project Plan

Status: target product/requirements contract
Last reviewed: 2026-08-02
Implementation status: prototype foundation; see code-backed audit

**Companion docs**

- [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md) — **active build blueprint** (modules, **TUI**, LLM switch, milestones M0–M8). Prefer it for day-to-day implementation detail.
- [`FLOW.md`](./FLOW.md) — **end-to-end TUI + system flows**.
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — **current committed code truth**, gaps, risks, configuration, and test coverage.
- This file — **full product/requirements plan**: US job-apply goals, modular work-auth packs, data model, workflows, safety, testing, MVP vs future.
- [`README.md`](./README.md) — docs index.
- [`../README.md`](../README.md) — short project summary.

If docs disagree on current behavior, `IMPLEMENTATION_STATUS.md` wins. For target stack or MVP order, `SYSTEM_ARCHITECTURE.md` is the authority until reconciled.

---

## 0. Current snapshot versus this contract

This file intentionally describes the desired product, including requirements that do not exist yet. At merge commit `f4176c7`, the strict profile, locally validated/private-AI onboarding, deterministic Apply retrieval, SQLite audit, generic Playwright worker, audit preview, and one-use submit claim exist as a tested foundation. OpenRouter powers onboarding and the Settings health check; the full suite passes 43 tests.

The following contract areas remain incomplete: exhaustive onboarding free-text privacy controls and explicit cloud-routing UX, real pack schemas, LM Studio, Apply agent runtime, vector RAG, ATS adapters, document build/hashing, browser restart recovery, retention/limits/metrics, enforced status transitions, and production-grade submit-time profile/live-page/blocker/URL checks. Supervised Submit should stay disabled outside controlled development fixtures.

---

## 1. Purpose

This project is a **local, single-user, Python TUI** system for **US-based job applications** that:

1. Interviews you to create one verified, human-readable **`PROFILE.md`**.
2. Keeps identity, SSN/document numbers, professional history, documents, policies, insights, and reusable portal Q&A in that file.
3. Stores site credentials, application state, field actions, events, checkpoints, and artifact paths in local SQLite.
4. Accepts a US career-page URL, logs in or creates an account with Playwright, requests OTP, and fills one field at a time from profile truth.
5. Pauses safely on CAPTCHA, consent, low confidence, or unknown questions.
6. Shows a source-linked final review and allows one supervised Submit click only after explicit approval.

**Scope:** United States roles and application flows only for now (US locations, US remote, or US-hiring career pages). Non-US country flows are out of scope for this phase.

**Work authorization is modular — not everyone needs STEM OPT / H-1B.**  
A US citizen, green-card holder, and F-1 STEM OPT candidate share the same core apply engine. Immigration-heavy logic lives in **optional profile packs** you turn on only if they apply to you. The system is decision support, not an immigration or employment-law authority: it must not invent status answers or overstate employer sponsorship / E-Verify conclusions.

The first release includes an **opt-in supervised submit**. Submission remains disabled by default and requires a matching preview hash plus a one-use approval. ATS board collection remains future work.

---

## 2. Goals and non-goals

### 2.1 MVP goals (build first)

- **US-only** apply workflow (filter/prefer US jobs; no multi-country product yet).
- Forced first-run onboard → strict Markdown profile + optional work-auth packs.
- Profile editor for personal data, professional history, documents, policies, and reusable portal Q&A.
- `apply <url>` for US career/application URLs: login/account creation, OTP pause, inventory, map, fill, evidence, preview, approve, and one supervised submit.
- Project-owned supervised agent runtime; LM Studio ↔ OpenRouter ↔ `off`.
- Exact local profile lookup first; disposable non-sensitive RAG index later.
- SQLite for credentials and application audit; `PROFILE.md` is profile truth.
- Pause on unknown / sensitive / CAPTCHA / OTP / consent.
- No fabricated answers; submit disabled until explicitly enabled.

### 2.2 Future goals (after MVP)

- US company/job discovery from approved Greenhouse, Lever, Ashby (etc.) public endpoints.
- Optional **pack-specific** eligibility helpers (e.g. STEM OPT evidence) — only when that pack is enabled.
- Explainable matching/scoring for US roles.
- Dashboard / notifications; email OTP reader; ATS-specific adapters.
- Postgres/queues only if needed.
- Later exploration: non-US markets as separate locale packs (not in current phase).

### 2.3 Non-goals for the MVP

- Unreviewed, repeated, or autonomous application submission.
- Building a product centered on STEM OPT / H-1B for every user.
- Legal conclusions about immigration, sponsorship, or employment eligibility.
- Bypassing CAPTCHA, bot detection, auth walls, or site restrictions.
- Scraping LinkedIn/Indeed/Google Jobs without approved access.
- Creating accounts or accepting terms without explicit user action.
- Guessing or enhancing resume/work-auth facts.
- Mass-applying with a generic resume.
- Multi-country job markets in this phase.
- Requiring a third-party agent CLI or a TypeScript runtime for the product.

---

## 3. Requirements analysis

The product has four concerns with different trust boundaries:

1. **`PROFILE.md`** — verified facts, SSN/document numbers, policies, documents, and reusable Q&A (highest sensitivity).
2. **SQLite application store** — plaintext site credentials by explicit policy, application state, events, field actions, checkpoints, and artifact paths.
3. **Agent reasoning** — onboarding, form mapping, and coaching with minimum necessary non-sensitive context.
4. **Browser apply** — Playwright against third-party career pages with PII, redacted evidence, and a one-use submit gate.
5. **Optional later: discovery & scoring** — public job data, evidence, and match explanations.

Runtime data defaults to the OS-local app-data directory outside the repository and OneDrive. Only profile services may rewrite `PROFILE.md`; the LLM cannot verify facts, and the browser cannot submit without a current approval.

### 3.1 Profile parts: core US apply + optional work-auth packs

Think of the profile as **Lego parts**. Everyone uses the same US apply engine. Extra immigration logic is optional.

```text
┌──────────────────────────────────────────────┐
│  CORE (always) — US job applications         │
│  identity, contact, education, work history, │
│  skills, resume PDF, location prefs (US),    │
│  salary, answer policies, apply-by-URL       │
└──────────────────────────────────────────────┘
         │ enable only what you need
         ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Pack: US_CITIZEN│ │ Pack: US_PR     │ │ Pack: OTHER_AUTH│
│ / work eligible │ │ (green card)    │ │ (generic visa / │
│ simple answers  │ │                 │ │  EAD / etc.)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │
         ▼  (only if relevant to you)
┌─────────────────┐ ┌─────────────────┐
│ Pack: F1_OPT    │ │ Pack: STEM_OPT  │  … future: H1B, etc.
│ standard OPT    │ │ + E-Verify /    │
│                 │ │   I-983 caution │
└─────────────────┘ └─────────────────┘
```

| Pack | Who it’s for | What it adds |
|---|---|---|
| *(none beyond core)* | Anyone applying to US jobs | Core facts only; work-auth questions answered from a simple `work_authorization` fact |
| `US_CITIZEN` | US citizens | Short verified answers for “authorized to work” / citizenship-style fields |
| `US_PR` | Permanent residents | PR/green-card oriented answers |
| `OTHER_US_AUTH` | Other US work-authorized statuses | Generic “authorized / needs sponsorship?” facts you verify |
| `F1_OPT` | F-1 OPT | OPT dates / related form answers (no STEM-specific employer evidence) |
| `STEM_OPT` | F-1 STEM OPT seekers | Extra questions + **optional** employer-evidence helpers; E-Verify = indicator only |
| `H1B` (future) | H-1B / sponsorship seekers | Sponsorship prefs + careful wording; not legal advice |

**Rules for packs**

1. Onboard asks: “Which US work-authorization situation fits you?” → enable 0+ packs.
2. Disabled packs: **no STEM/H-1B questions**, no E-Verify scoring, no extra RAG noise.
3. Forms asking visa/sponsorship: answer only from enabled-pack verified facts or **ask the user** — never invent.
4. OTP (one-time passcode on a career site) is unrelated to “OPT” — it is always part of the **core apply** pause flow.

#### STEM OPT pack notes (only when `STEM_OPT` enabled)

STEM OPT employer fit is not a single company boolean. Guidance involves E-Verify participation, Form I-983, bona fide employer-employee relationship, and supervision. Sources: [USCIS](https://www.uscis.gov/node/92821), [E-Verify FAQ](https://www.e-verify.gov/faq/am-i-required-to-participate-in-e-verify-in-order-to-hire-f-1-students-who-seek-a-stem-opt), [Form I-983 overview](https://studyinthestates.dhs.gov/form-i-983-overview).

If/when this pack’s eligibility helper exists, store independent evidence and outcomes such as `verified_compatible`, `likely_compatible`, `unknown`, `likely_incompatible`, `incompatible`. **E-Verify is an indicator, not a guarantee.** Retain source, date, matched name, method, confidence. Never show STEM scoring UI to users who did not enable this pack.

### 3.2 Open or risky requirements

- **US-only phase:** remote-US / US-located / US-hiring pages; do not build multi-country routing yet.
- **URL-first vs boards:** MVP is paste-a-URL; board crawlers future.
- **“Any career page”:** best-effort within US ATS/career sites.
- **Submission consent:** per-application review and preview-hash approval; one Submit click; no blind retry.
- **Pack selection:** must be explicit; changing packs re-runs relevant onboard questions.
- **Sensitive voluntary forms:** `decline_to_answer`, `manual_only`, or verified value.
- **AI data handling:** lmstudio local vs openrouter cloud; schema-validate; no training on candidate data.
- **Email OTP:** future; SMS manual. (OTP ≠ OPT.)
- **Retention/deletion** and **legal review** before live submit / aggressive collection.

---

## 4. System architecture and decisions

### 4.1 MVP architecture: Python modular app + TUI

Single Python package, local process, **Textual TUI** as the primary UI:

```text
User (Terminal TUI)
   |
   v
Textual App (screens) ──> Apply orchestrator (state machine + gates)
   |                            |
   |                            +──> Playwright browser worker
   v
Agent runtime (typed planning + permission gates)
   |  roles: onboarder | form_mapper | coach
   |  tools + permission allowlists
   v
OpenAI-compatible client
   |---- LLM_PROVIDER=lmstudio  --> http://localhost:1234/v1
   |---- LLM_PROVIDER=openrouter --> https://openrouter.ai/api/v1
   '---- LLM_PROVIDER=off       --> no model calls

PROFILE.md (profile truth + reusable Q&A)
SQLite (credentials, jobs, applications, events, checkpoints)
Disposable local index (optional non-sensitive RAG)
files/ (documents + redacted artifacts)
```

Screen flows: [`FLOW.md`](./FLOW.md). Package layout: `SYSTEM_ARCHITECTURE.md`.

### 4.2 Core decisions

- **Python only** for this product; **Textual TUI** as primary UX.
- **`PROFILE.md` is the only profile source of truth;** strict YAML front matter plus readable Markdown.
- **SQLite** stores plaintext site credentials by explicit policy and all application/audit state; Postgres is optional later.
- **In-process orchestration** for MVP; Redis/BullMQ only if needed later.
- **Project-owned agent runtime** with explicit tools, typed plans, and permission gates.
- **LLM_PROVIDER switch:** `lmstudio` | `openrouter` | `off` — one OpenAI SDK factory.
- **Playwright** for browser; model returns fill **plans**; Python executes under gates.
- **Retrieval order:** exact structured lookup → local search/RAG → minimal agent context → ask the user.
- **Sensitive profile fields:** deterministic local lookup only; never RAG or cloud-model context.
- **Rules + verified facts before model guesses;** model never auto-verifies facts or submits.
- **Submit latch:** disabled by default; current preview hash + explicit approval + one-use claim before one click.
- **URL-first apply;** ATS board connectors deferred.

### 4.3 Trust boundaries

| Component | Public job/page data | Candidate PII | Secrets | Browser state | Can submit |
|---|---:|---:|---:|---:|---:|
| TUI / orchestrator | Yes | Yes | Session-only display | No | Grants one-use approval |
| Agent runtime + LLM | Redacted/minimal | Minimal projection | Provider key if OpenRouter | No | No |
| `PROFILE.md` service | No | Yes, including SSN/docs | No credentials | No | No |
| SQLite store | Metadata | Application values | Plaintext site credentials | Checkpoints | Claims one-use gate |
| Playwright worker | Selected page | Minimum required | Runtime-injected | Yes | One click after claimed approval |
| Future collectors | Read/write public | No | Source-specific only | No | No |

---

## 5. Modules and responsibilities

Names map to Python packages directly under `src/` (see §12 and `SYSTEM_ARCHITECTURE.md`).

### 5.1 MVP modules

#### `profile`

- Strict `PROFILE.md` parser, validator, atomic writer, backup recovery, and content hash.
- Personal details, professional history, SSN/document numbers, answer policies, insights, and reusable portal Q&A.
- **Enabled packs** list on the profile (e.g. `US_CITIZEN`, `STEM_OPT`).
- Pack-specific onboard questions only when enabled.
- Resume/document metadata and paths.
- Model output never auto-verifies facts.

#### `llm`

- OpenAI-compatible client factory for LM Studio and OpenRouter.
- Provider enable flags + `LLM_PROVIDER` active switch.
- JSON-plan fallback when tool-calling is unreliable.

#### `agent`

- Project-owned runtime loop with explicit tool permissions.
- Roles: `onboarder`, `form_mapper`, `coach`.
- Tool registry + permission allowlists.

#### `rag` (optional early, required useful by mapper polish)

- Build a disposable index from non-sensitive verified profile chunks and portal Q&A.
- Exact `PROFILE.md` lookup always wins; SSN/document values never enter the index.

#### `browser`

- Playwright open URL, login/account creation, OTP/CAPTCHA/consent pause, field inventory/fill, and redacted screenshots.
- Consume a matching one-use approval before exactly one Submit click; ambiguous results are never retried.

#### `apply`

- Application state, profile snapshot hash, field sources/confidence, preview hash, approve, OTP inject, and one-use submit gates.

#### `tui`

- First launch: Onboard. Ready navigation: Profile, Apply, Applications, Settings.
- No business logic in widgets — call `profile` / `apply` / `llm` services.
- Full flows in [`FLOW.md`](./FLOW.md).

#### `cli` (optional later)

- Thin Typer wrappers around the same services for scripting; not required for MVP.

### 5.2 Future modules (deferred)

- `company-discovery`, `ats-connectors` (Greenhouse → Lever → Ashby → …), `job-collector`, `job-normalizer`, `job-matcher`, notifications channels, dashboard UI, scheduler/outbox.

Connector governance (when built): registry with access class, terms review, rate limits, no evasion on `401`/`403`/`429`. Conceptual contract becomes a Python protocol, not TypeScript.

---

## 6. Connector contract and source governance (future)

When board collection is added, each source needs:

- source name/owner; access class (`official_api`, `public_feed`, `structured_page`, `browser`);
- allowed operations; auth/secret refs; terms review; interval/burst/timeout;
- retention; connector version; enabled flag; circuit-breaker policy.

Unknown/unreviewed sources stay disabled. Access challenges reduce/stop traffic and create review — no evasion.

Initial future order if/when enabled: Greenhouse public Job Board API → Lever postings → Ashby public postings → others after policy review. LinkedIn/Indeed remain off without approved access.

---

## 7. Data model

Runtime data defaults to the OS-local app-data directory, outside the repository and synced workspace.

### 7.1 `PROFILE.md` (only profile source of truth)

Strict YAML front matter provides machine-safe values; generated Markdown sections provide a readable professional record. Atomic replacement and one backup protect updates.

- metadata: schema version, draft/complete status, timestamps, verification
- identity/contact and structured location
- `sensitive_identity`: SSN and government-document numbers
- professional summary, education, work history, projects, and skills
- work authorization and enabled packs
- documents/resume paths and hashes
- common answers, answer policies, user insights, verification, and provenance
- portal Q&A: normalized intent, observed wording, answer, scope, company, verification, and usage timestamps

Sensitive identity is available only to deterministic local mapping. It is excluded from RAG and cloud-model context.

### 7.2 SQLite application store

#### `credentials`

- one row per domain; email, username, and **plaintext password by explicit product decision**
- database is OS-local and restricted to the current user where the platform allows
- password values never enter events, screenshots, model context, or `PROFILE.md`

#### `runtime_settings`

- persisted local switches such as supervised-submit enablement

#### `jobs`

- From URL apply (and later from collectors): `title`, `company_name`, `application_url`, `source_url`, `description_text`, `ats_hint`, `market` default `US`, timestamps, `active`

#### `applications`

- URL/company, status, exact `PROFILE.md` content hash, preview hash, timestamps

#### `field_actions` / `application_events`

- field label/question, redacted-or-plain value, value hash, profile source, confidence, outcome
- ordered click/fill/login/OTP/review/submit events; password, OTP, and sensitive values are redacted

#### `browser_checkpoints` / `artifacts`

- resumable step + URL + state JSON
- redacted screenshot/artifact paths captured through the application

#### `submit_approvals`

- preview hash, approval time, and consumed time
- one approval can claim at most one Submit click

### 7.3 Future tables (discovery / scoring)

Keep the earlier rich model as the target when collectors ship:

- `companies`, `company_aliases`, `company_sources`, `company_evidence`, `company_eligibility_assessments`
- `source_fetch_runs`, `raw_jobs`, `job_versions`, `job_aliases`
- `match_evaluations`, `model_runs`, `company_preferences`
- infra: `outbox_events`, `scheduled_runs`, `source_access_policies`, `notifications`, `dead_letter_items`

Claim types for evidence (mostly **STEM_OPT / sponsorship packs**, future): `everify_enrollment`, `i983_willingness`, `employer_relationship`, `h1b_history`, `remote_policy`, `work_authorization_policy`.

---

## 8. Status machines

Persist lowercase machine values; TUI shows friendly labels.

| User-facing status | Owning record | Stored value |
|---|---|---|
| Discovered | Job | `discovered` |
| Scored | Job | `scored` (future matching) |
| Rejected by filter | Job/match | `rejected_by_filter` (future) |
| Ready to apply | Application | `ready_to_apply` |
| Applying | Application | `applying` |
| Waiting for OTP | Application | `waiting_for_otp` |
| Waiting for an answer | Application | `waiting_for_user_answer` |
| Waiting for user review | Application | `waiting_for_user_review` |
| Approved | Application | `approved` |
| Submitting | Application | `submitting` |
| Submission uncertain | Application | `submission_uncertain` |
| Blocked by CAPTCHA | Application | `blocked_by_captcha` |
| Failed | Application | `failed` |
| Cancelled | Application | `cancelled` |
| Submitted | Application | `submitted` |
| Closed | Job/application | `closed` |
| Interview / Rejected / Offer | Application | `interview` / `rejected` / `offer` |

### 8.1 Job lifecycle

**MVP (URL ingest):**

```text
discovered (from URL) -> applying path via application
```

**Future (collectors):**

```text
discovered -> normalized -> scored -> ready_to_apply
                              |  \-> review
                              \----> rejected_by_filter
any open state -> closed -> reopened (if observed again)
```

### 8.2 Application lifecycle

```text
ready_to_apply -> applying -> waiting_for_user_answer -> applying
                         | -> waiting_for_otp -> applying
                         | -> blocked_by_captcha -> applying (manual resume)
                         | -> waiting_for_user_review -> approved -> submitting
                         |                                      | -> submitted
                         |                                      \ -> submission_uncertain
                         \ -> cancelled
```

Target requirement: every transition is validated and written to `application_status_history` with timestamp, actor, correlation ID, and reason, and `submitted` never returns to `applying`. Current code stores a status string directly on `applications`, accepts free-form transitions, and has no status-history table.

### 8.3 Supervised submission gates

All must pass before an irreversible submit click:

1. Env + DB policy allow submission (`APPLICATION_SUBMISSION_ENABLED`).
2. Not already submitted locally or visibly confirmed remotely.
3. URL/title/company still match.
4. Every required answer comes from `PROFILE.md` or explicit user input.
5. No CAPTCHA, pending OTP, consent, unknown, or validation error.
6. Preview hash matches explicit user approval.
7. Approval is atomically claimed and consumed before clicking.
8. Exactly one click is attempted; uncertain outcomes require manual reconciliation.

---

## 9. End-to-end workflows

### 9.1 Onboarding

1. Missing, invalid, incomplete, or unverified `PROFILE.md` routes directly to Onboard.
2. Collect structured identity/contact/location, professional history, skills, work authorization, optional SSN/document numbers, and resume path.
3. Save an atomic draft after every answer; never echo sensitive answers.
4. User reviews the readable file and types `VERIFY`.
5. Returning launches show only Profile, Apply, Applications, and Settings.

### 9.2 Apply by URL

1. Create an application bound to the current `PROFILE.md` content hash.
2. Load/save the site credential in SQLite; password is plaintext but excluded from logs.
3. Playwright opens the URL, fills login/account fields, and pauses for consent, CAPTCHA, or OTP.
4. Inventory each field. Resolve exact structured data first, reusable Q&A/search second, minimal agent context later, then ask the user.
5. A confirmed reusable answer updates `PROFILE.md`; one-off answers remain application data.
6. Fill field by field, recording source, confidence, value hash, event, screenshot, and checkpoint.
7. Build a preview hash and show values, sources, and evidence in Applications.
8. User approves that exact preview. If supervised submit is enabled, consume approval and click once.
9. Capture confirmation; ambiguous result becomes `submission_uncertain` and is never retried automatically.

Detail diagrams: [`FLOW.md`](./FLOW.md).

### 9.3 Future apply improvements

ATS-specific adapters, stronger browser recovery, email OTP integration, document compilation, and semantic RAG improve this same guarded flow without weakening review or submit gates.

### 9.4 Future discovery / monitoring / matching

Preserve the earlier detailed collector and scoring workflows as post-MVP:

- discovery → normalize → dedupe → version → close-with-grace;
- hard filters then weighted score with explanations;
- work-auth / sponsorship components **only if** relevant packs are enabled;
- STEM evidence unknown forces review **only** for `STEM_OPT` pack users;
- example score components (role 20, skills 25, experience/education 15, location 10, work-auth/pack 15 when enabled else redistributed, resume 10, comp 5).

Scores are recommendations, not probabilities or immigration/employment guarantees.

---

## 10. Interface design

### 10.1 MVP: TUI (primary)

Fullscreen Textual app. Screens and flows: [`FLOW.md`](./FLOW.md).

| Screen | Main actions |
|---|---|
| Onboard | Forced first-run interview, atomic draft, review, verify |
| Profile | All user facts, SSN/docs, history, packs, documents, reusable Q&A |
| Apply | URL, site credential, OTP, field retrieval, browser fill |
| Applications | Values/sources/evidence, approve, one supervised Submit click |
| Settings | LLM switch, local paths, submit policy |

### 10.2 Optional later: script CLI / REST

Thin Typer or `/api/v1` may wrap the same services. Not required for MVP.

---

## 11. Concurrency and events

**MVP:** single-user local process; SQLite transactions; no Redis required.

**Later:** outbox + queues (`jobs.collect`, `applications.dry_run`, …) if scheduling/multi-worker appears. Never put secrets, resumes, full answers, or browser storage in a queue payload. Non-retryable: validation, CAPTCHA, auth walls, ambiguous submit, unknown answers until human action.

---

## 12. Recommended folder structure

```text
terminal_hire/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ docs/
│  ├─ README.md              # docs index
│  ├─ FLOW.md
│  ├─ SYSTEM_ARCHITECTURE.md
│  ├─ PROJECT.md
│  ├─ adr/
│  ├─ runbooks/
│  └─ threat-model/
├─ src/
│  ├─ __main__.py            # launch TUI
│  ├─ app.py                 # Textual App
│  ├─ tui/                   # screens only
│  ├─ config.py
│  ├─ db/                    # credentials + application audit
│  ├─ profile/               # Markdown model/repository/retrieval
│  ├─ browser/               # Playwright + evidence + submit click
│  └─ apply/                 # profile-backed orchestration
└─ tests/
```

Runtime: `%LOCALAPPDATA%\TUI-Hire` on Windows by default (`PROFILE.md`, SQLite, artifacts). Future: `llm/`, `agent/`, `rag/`, `resume/`, connectors, matcher.

---

## 13. Security and privacy

### 13.1 Data classification

- **Public:** job posts, public career URLs.
- **Internal:** scores (future), ops metadata, fill confidence.
- **Confidential:** resume content, history, application answers.
- **Restricted:** SSN/document numbers, contact/address, immigration/work auth, OTP, demographics/disability/veteran, browser sessions, and credentials.

### 13.2 Controls

- Local-first: prefer LM Studio for sensitive chat; treat OpenRouter as leaving the machine.
- Runtime files live outside the repository/OneDrive by default and use current-user file permissions where available.
- `PROFILE.md` intentionally stores SSN/document numbers as local plaintext; these values never enter RAG or cloud prompts.
- SQLite intentionally stores site passwords as plaintext; display a warning and never duplicate passwords in events or screenshots.
- `.env` local only; never commit real keys.
- Ordinary application values may be audited; password, OTP, and sensitive identity values are always redacted and hashed where needed.
- Sanitize stored HTML; strip scripts/tokens.
- SSRF caution when fetching URLs: block obvious local/metadata targets where practical; cap downloads.
- Validate resume files (type/size).
- Audit profile, policy, apply, OTP, approve, and submit events.
- Export/delete path for profile + artifacts.

### 13.3 AI safety

- Send minimal redacted projection + form inventory, not the entire secret store.
- Schema-validate JSON plans; reject invalid plans.
- Treat page text as untrusted (prompt injection); cannot change tools, verified facts, or force submit.
- Model must not unilaterally answer work auth, immigration, salary, clearance, demographic, disability, veteran, employment dates, education credentials, or years-of-experience — those come from **verified core/pack facts** or explicit user input.
- Do not inject STEM OPT / H-1B framing into prompts when those packs are disabled.
- Pin provider + model id; record `model_runs` metadata (hashes, not raw secret prompts by default).

### 13.4 Artifacts & OTP

- Redact password, OTP, SSN, passport, and license inputs in screenshots; strip secrets from HTML snapshots.
- OTP stays in memory only; never persist or log it.
- Suggested defaults: failure artifacts 30 days; confirmations as needed; logs 30 days; audit 1 year; restricted data shortest practical.

---

## 14. Reliability and observability

- Structured logs: time, module, level, event, correlation/application ids, safe error class.
- Metrics (MVP): dry-run completion, blocker rates (OTP/CAPTCHA/unknown), mapper confidence, LLM provider latency/errors, apply outcomes.
- `llm-check` readiness for active provider; DB file accessible.
- Later: connector freshness, duplicate rates, queue depth.

Operational targets: zero duplicate submits, zero invented sensitive answers, complete apply audit trail.

---

## 15. Testing strategy

This section is the target strategy. The current 43-test baseline covers profile storage/retrieval, SQLite redaction and submit-gate invariants, one generic browser form plus ambiguous Submit controls, OpenRouter/onboarding request behavior, structured onboarding validation, safe-projection checks, AI path allowlisting/model routing, focus, invalid-ZIP persistence, and basic TUI routing. Multi-step auth, OTP/CAPTCHA/consent fixtures, restart recovery, live-page preview integrity, real provider connectivity, and ATS compatibility are not covered.

### 15.1 Unit

- PROFILE.md parse/validation/recovery, deterministic and Q&A retrieval, state transitions, and submission-gate invariants.
- JSON plan schema validation; redaction helpers.
- Resume compile dry path (mock or CI TeX where available).

### 15.2 LLM client

- Mock OpenAI-compatible server for lmstudio/openrouter shapes.
- Provider switch selects correct base URL/model.
- Invalid tool/JSON plans rejected.

### 15.3 Browser

- Local synthetic forms: text, select, checkbox, file upload, multi-step, OTP, CAPTCHA placeholder, confirmation.
- Verify submit is impossible without a matching unconsumed approval.
- Verify one approval permits one click and ambiguous results never retry.
- Pause/resume, selector drift, crash recovery, and screenshot redaction.

### 15.4 Acceptance (MVP)

- Onboard creates a strict verified `PROFILE.md` and masks sensitive answers.
- LaTeX → PDF registered as document.
- `apply <url>` on a synthetic page logs in, inventories fields, fills from profile sources, and produces evidence plus preview.
- CAPTCHA/unknown/OTP pause without automated bypass.
- Applications shows values/sources/artifacts; exact preview approval permits one supervised Submit click when enabled.
- Switching `LLM_PROVIDER` does not change DB schema or Playwright gates.

---

## 16. Deployment strategy

### 16.1 Local development (MVP)

- Python 3.11+ venv / uv; Playwright browsers installed locally.
- Target: LM Studio running when `LLM_PROVIDER=lmstudio`; OpenRouter key when using cloud. Current code supports only the OpenRouter health check and standalone client.
- OS-local app-data directory with `PROFILE.md`, SQLite, and artifacts; no Docker required.
- Synthetic profile/fixtures only in tests.

### 16.2 Later production-ish

- Private workstation or VM; encrypted disk; optional Postgres + object storage.
- `production-observe`: real URLs, dry-run forced.
- `production-submit`: only after security review, soak, backups, explicit user policy.

---

## 17. Milestones

Aligned with `SYSTEM_ARCHITECTURE.md` (canonical numbering M0–M8):

| Milestone | Focus | Exit |
|---|---|---|
| **M0** | Python/Textual shell and local-data decisions | Implemented |
| **M1** | Strict `PROFILE.md`, parser/recovery/retrieval, first-run onboarding, profile editor | Implemented foundation with private-AI validation/review |
| **M2** | SQLite credentials/audit, application orchestration, evidence, one-use submit gate | Experimental foundation; P0 submit checks remain |
| **M3** | LaTeX → PDF | Uploadable resume |
| **M4** | Harden Playwright inventory/fill/login against ATS fixtures | E2E synthetic and selected real pages |
| **M5** | LM Studio/OpenRouter agent + disposable non-sensitive RAG | OpenRouter onboarding only; Apply agent, LM Studio, and index planned |
| **M6** | OTP/CAPTCHA/consent recovery across browser restarts | Interrupted applies recoverable |
| **M7** | Harden supervised submit | Security review + synthetic confirmation coverage |
| **M8** | ATS collectors, matching, email OTP, UI, scale-out | As needed |

Older TS/Postgres/dashboard-first milestones are **withdrawn** as the MVP path.

---

## 18. MVP versus future scope

### MVP

Target MVP scope, not a list of completed features:

- Single user, one verified Markdown profile (TUI onboard).
- SQLite application audit + plaintext site credentials; optional disposable local index.
- Python **Textual TUI** + supervised agent runtime + LM Studio ↔ OpenRouter.
- LaTeX resume → PDF.
- URL-first Playwright login/fill; preview; OTP/CAPTCHA/consent pause.
- Opt-in one-click supervised submit; no CAPTCHA solve; no LinkedIn/Indeed scraping; no required cloud except optional OpenRouter.

### Future

- Greenhouse/Lever/Ashby (then more) collectors; eligibility evidence; scoring dashboard.
- Email OTP integration and stronger supervised-submit recovery; no unreviewed autopilot.
- Postgres, Redis, multi-process workers, hosted UI.
- Multiple profiles/users only if needed.

---

## 19. What should be built first

1. Add submit-time profile/live-page/blocker/URL validation, legal status transitions, and daily limits.
2. Expand synthetic Playwright pages for login, account creation, OTP, CAPTCHA, consent, multi-step fill, redirects, validation, and confirmation.
3. Add browser restart recovery and canonical current-field reconciliation.
4. Strengthen onboarding free-text redaction/cloud-consent UX and integrate a schema-validated mapper.
5. Decide whether LM Studio and vector RAG remain MVP requirements; implement only if retained.
6. Add real pack schemas plus LaTeX/PDF document validation, build, and hashing.
7. Harden ATS-specific selectors only after the safety and recovery gates are proven.

This keeps the URL-first product intent while putting submit integrity and browser recovery ahead of expansion work.

---

## 20. Unresolved technical and product decisions

| Decision | Options | Recommendation for now |
|---|---|---|
| Default `LLM_PROVIDER` | lmstudio; openrouter; off | Currently `lmstudio`, although its adapter is absent; reconsider `off` until integrated |
| LM Studio model | user-loaded id | Prefer a model decent at JSON / tools |
| OpenRouter model | catalog slug | Start with a mid-cost strong JSON model; pin id |
| Embeddings | LM Studio; fastembed local; OpenRouter | **Local** (`fastembed` or LM Studio) even if chat is OpenRouter |
| Package/tooling | uv; poetry; pip | `uv` or plain `pyproject.toml` + pip |
| ORM | SQLModel; SQLAlchemy; raw SQL | Raw `sqlite3` currently implemented |
| LaTeX engine | tectonic; MiKTeX; TeX Live | Whatever is installed; document in README |
| Vector DB | Chroma; LanceDB; none until M5 | None currently; add only if lexical retrieval is insufficient |
| Submission consent | Per-job; allowlist autopilot | Per-job approve for first live release |
| Browser profile | Persistent; ephemeral | Ephemeral session + SQLite checkpoints currently |
| Notifications | TUI only; email; desktop | TUI first |
| UI | Textual TUI; optional script CLI; web later | **Textual TUI** |
| Retention | Fixed; configurable | Conservative defaults |
| Hosting | Local workstation; VM | Local first |
| Daily limits | Fixed; profile policy | Low ceiling when submit exists |
| E-Verify / STEM helpers | Off; pack-only hybrid | **Off unless `STEM_OPT` pack enabled** |
| Default work-auth packs | None; citizen; OPT; … | Ask at onboard; default **none extra** until user picks |

---

## 21. Assumptions

- One candidate user applying to **US** roles.
- Work-auth complexity is optional via packs; many users only need core + simple “authorized to work in the US” facts.
- User verifies facts/documents before dry-runs on real sites.
- Career URLs are for personal US apply workflow; respect site terms; no evasion.
- “Any page” apply is best-effort; failures pause for the user.
- Never overstate sponsorship / E-Verify / STEM conclusions; unused packs stay silent.
- OTP means one-time passcode on a site; OPT means Optional Practical Training — keep them separate in UX copy.
- Clocks UTC; display default `America/Chicago` unless profile overrides.
- Supervised submit is disabled by default; user enables policy and approves each exact preview.

---

## 22. Success measures

- Onboard completion → core required fields verified; only enabled-pack fields required extra.
- Resume PDF build success rate.
- Dry-run completion rate; unknown-field / CAPTCHA / OTP / selector-drift rates by site/ATS hint.
- Mapper never pulls disabled-pack facts into plans.
- Zero fabricated sensitive answers, duplicate submits, CAPTCHA bypasses, or secret leaks.
- Median time from blocker to user resolution.
- (Future) discovery/match metrics; STEM pack evidence quality **only** for users who enabled it.

---

## 23. Definition of done for planning

This document, `SYSTEM_ARCHITECTURE.md`, and `FLOW.md` are the active product contract (not legal approval). Keep code, README, `.env.example`, storage policy, and submit gates consistent with them.

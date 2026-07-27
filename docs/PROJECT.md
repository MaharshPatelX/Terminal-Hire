# Terminal-Hire — Project Plan

Status: planning baseline (aligned with active architecture)  
Last reviewed: 2026-07-26  
Implementation status: not started  

**Companion docs**

- [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md) — **active build blueprint** (modules, **TUI**, LLM switch, milestones M0–M8). Prefer it for day-to-day implementation detail.
- [`FLOW.md`](./FLOW.md) — **end-to-end TUI + system flows**.
- This file — **full product/requirements plan**: US job-apply goals, modular work-auth packs, data model, workflows, safety, testing, MVP vs future.
- [`README.md`](./README.md) — docs index.
- [`../README.md`](../README.md) — short project summary.

If the two docs ever disagree on **stack or MVP order**, `SYSTEM_ARCHITECTURE.md` wins until both are updated together.

---

## 1. Purpose

This project is a **local, single-user, Python TUI** system for **US-based job applications** that:

1. Interviews you to build a **verified candidate profile** (core facts + optional packs).
2. Stores a **LaTeX resume** and compiles it to PDF for uploads.
3. Accepts a **US career-page / job URL**, opens it with Playwright, maps the form to your facts, and **dry-runs** an application (preview first).
4. Pauses safely on OTP, CAPTCHA, consent, or unknown questions.
5. Optionally later: supervised submit, US job-board discovery, scoring, and a richer UI.

**Scope:** United States roles and application flows only for now (US locations, US remote, or US-hiring career pages). Non-US country flows are out of scope for this phase.

**Work authorization is modular — not everyone needs STEM OPT / H-1B.**  
A US citizen, green-card holder, and F-1 STEM OPT candidate share the same core apply engine. Immigration-heavy logic lives in **optional profile packs** you turn on only if they apply to you. The system is decision support, not an immigration or employment-law authority: it must not invent status answers or overstate employer sponsorship / E-Verify conclusions.

Long-term goals may include policy-controlled submission and ATS board collection. The **first release stops before live submit**: profile, resume, URL inventory, field mapping, dry-run fill, and review artifacts must work first.

---

## 2. Goals and non-goals

### 2.1 MVP goals (build first)

- **US-only** apply workflow (filter/prefer US jobs; no multi-country product yet).
- Guided onboard → **core profile** + enable only the **work-auth packs** you need.
- LaTeX → PDF resume pipeline for career-page uploads.
- `apply <url>` for US career/application URLs: inventory, map, dry-run fill, preview, approve.
- Own agent runtime (Grok Build–inspired); LM Studio ↔ OpenRouter ↔ `off`.
- Optional Chroma RAG; SQLite source of truth.
- Pause on unknown / sensitive / CAPTCHA / OTP / consent.
- No fabricated answers; dry-run latch on.

### 2.2 Future goals (after MVP)

- US company/job discovery from approved Greenhouse, Lever, Ashby (etc.) public endpoints.
- Optional **pack-specific** eligibility helpers (e.g. STEM OPT evidence) — only when that pack is enabled.
- Explainable matching/scoring for US roles.
- Dashboard / notifications; email OTP reader; supervised submit.
- Postgres/queues only if needed.
- Later exploration: non-US markets as separate locale packs (not in current phase).

### 2.3 Non-goals for the MVP

- Live application submission.
- Building a product centered on STEM OPT / H-1B for every user.
- Legal conclusions about immigration, sponsorship, or employment eligibility.
- Bypassing CAPTCHA, bot detection, auth walls, or site restrictions.
- Scraping LinkedIn/Indeed/Google Jobs without approved access.
- Creating accounts or accepting terms without explicit user action.
- Guessing or enhancing resume/work-auth facts.
- Mass-applying with a generic resume.
- Multi-country job markets in this phase.
- Requiring xAI cloud / `grok` CLI / TypeScript for the product.

---

## 3. Requirements analysis

The product has four concerns with different trust boundaries:

1. **Profile & documents** — verified facts, policies, LaTeX/PDF (highest sensitivity).
2. **Agent reasoning** — onboarding, form mapping, coaching via LM Studio or OpenRouter (minimum necessary context only).
3. **Browser apply** — Playwright against third-party career pages (PII in browser; gated submit).
4. **Optional later: discovery & scoring** — public job data, evidence, match explanations.

Modules share one local database but must not give the LLM or browser unrestricted power to rewrite verified facts or submit without gates.

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
- **Submission consent:** per-application approve for first live release; MVP forced dry-run.
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
Agent runtime (Grok Build–inspired)
   |  roles: onboarder | form_mapper | coach
   |  tools + permission allowlists
   v
OpenAI-compatible client
   |---- LLM_PROVIDER=lmstudio  --> http://localhost:1234/v1
   |---- LLM_PROVIDER=openrouter --> https://openrouter.ai/api/v1
   '---- LLM_PROVIDER=off       --> no model calls

SQLite (facts, jobs, applications, audit)
Chroma (optional RAG)
files/ (LaTeX, PDF, artifacts)
```

Screen flows: [`FLOW.md`](./FLOW.md). Package layout: `SYSTEM_ARCHITECTURE.md`.

### 4.2 Core decisions

- **Python only** for this product; **Textual TUI** as primary UX.
- **SQLite first** as source of truth; Postgres optional later.
- **In-process orchestration** for MVP; Redis/BullMQ only if needed later.
- **Own agent runtime** inspired by Grok Build; no `grok` / `xg-agent-sdk` requirement.
- **LLM_PROVIDER switch:** `lmstudio` | `openrouter` | `off` — one OpenAI SDK factory.
- **Playwright** for browser; model returns fill **plans**; Python executes under gates.
- **Rules + verified facts before model guesses;** model never auto-verifies facts or submits.
- **Dry-run latch:** `APPLICATION_SUBMISSION_ENABLED=false` plus explicit approve before any future submit.
- **URL-first apply;** ATS board connectors deferred.

### 4.3 Trust boundaries

| Component | Public job/page data | Candidate PII | Secrets | Browser state | Can submit |
|---|---:|---:|---:|---:|---:|
| TUI / orchestrator | Yes | Yes | Via config refs | No | Policy only (future) |
| Agent runtime + LLM | Redacted/minimal | Minimal projection | Provider key if OpenRouter | No | No |
| Profile/DB layer | Metadata | Yes (encrypted where needed) | Field keys | No | No |
| Playwright worker | Selected page | Minimum required | Runtime-injected | Yes | Future policy only |
| Future collectors | Read/write public | No | Source-specific only | No | No |

---

## 5. Modules and responsibilities

Names map to Python packages under `src/terminal_hire/` (see §12 and `SYSTEM_ARCHITECTURE.md`).

### 5.1 MVP modules

#### `profile`

- Versioned facts and answer policies; explicit verification for apply-eligible facts.
- **Enabled packs** list on the profile (e.g. `US_CITIZEN`, `STEM_OPT`).
- Pack-specific onboard questions only when enabled.
- Document metadata; LaTeX + PDF paths.
- Model output never auto-verifies facts.

#### `resume`

- Store `.tex`; compile to PDF (tectonic / latexmk / MiKTeX).
- Register primary PDF for upload fields.

#### `llm`

- OpenAI-compatible client factory for LM Studio and OpenRouter.
- Provider enable flags + `LLM_PROVIDER` active switch.
- JSON-plan fallback when tool-calling is unreliable.

#### `agent`

- Runtime loop inspired by Grok Build.
- Roles: `onboarder`, `form_mapper`, `coach`.
- Tool registry + permission allowlists.

#### `rag` (optional early, required useful by mapper polish)

- Embed verified chunks, job text, past Q&A into Chroma.
- Exact SQLite facts always win for email/phone/dates/immigration.

#### `browser`

- Playwright open URL, detect login/CAPTCHA/OTP, inventory fields, fill, upload PDF, capture redacted artifacts.
- Network guard: no submit in MVP.

#### `apply`

- Application state machine, preview hash, approve, OTP inject, gates.

#### `tui`

- Textual screens: Home, Onboard, Profile, Resume, Apply, Apps, Settings.
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

**MVP store:** SQLite (JSON columns where useful). **Later:** Postgres if needed. Use UUID PKs, UTC timestamps, enums/checks, `created_at`/`updated_at`, version columns for user-edited rows. Encrypt highly sensitive values at the application layer. Large artifacts live as files under `data/` (or encrypted object storage later).

### 7.1 MVP tables (implement first)

#### `candidate_profiles`

- `id`, `display_name`, `status`, `timezone`, `locale`
- `target_market`: `US` (fixed for this phase)
- `enabled_packs` JSON list (e.g. `["US_CITIZEN"]` or `["F1_OPT","STEM_OPT"]`)
- `submission_policy`, `profile_version`, timestamps

#### `profile_facts`

- `id`, `profile_id`, `category`, `field_key`
- optional `pack_id` (null = core; else fact belongs to that pack)
- encrypted or JSON value; `sensitivity`, `verification_status`
- `verified_at`, `source`, validity window, `allowed_uses`

**Core facts:** personal/contact, education, employment, projects, skills, US location prefs, salary, preferences, basic work-auth summary.  
**Pack facts:** only when that pack is enabled (citizenship details, OPT dates, STEM prefs, sponsorship prefs, etc.). Append versions; do not silently overwrite.

#### `answer_policies`

- `question_key` / pattern; `policy`: `verified_answer | decline | manual_only | never_answer`

#### `documents`

- `document_type`, `label`, paths for `.tex` / PDF, `sha256`, `mime_type`, `role_tags`, `active`

#### `jobs`

- From URL apply (and later from collectors): `title`, `company_name`, `application_url`, `source_url`, `description_text`, `ats_hint`, `market` default `US`, timestamps, `active`

#### `applications`

- `profile_id`, `job_id`, `status`, `status_reason`
- `selected_document_id`, `application_url`, `preview_hash`
- `idempotency_key`, attempt counters, `external_application_id`, `submitted_at`
- Unique `(profile_id, job_id)` when job id exists; for pure URL applies use stable URL hash identity.

#### `application_attempts` / `form_snapshots` / `field_mappings`

- Inventory JSON, mapper plan, outcomes, artifact paths, human_action_required

#### `application_status_history` / `blockers` / `audit_events` / `review_tasks`

- Full audit of transitions, OTP/CAPTCHA/unknown blockers, immutable audit log

### 7.2 Future tables (discovery / scoring)

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
| Waiting for user review | Application | `waiting_for_user_review` |
| Blocked by CAPTCHA | Application | `blocked_by_captcha` |
| Failed | Application | `failed` |
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
ready_to_apply -> applying -> waiting_for_user_review -> (approve) -> applying
                         | -> waiting_for_otp -> applying
                         | -> blocked_by_captcha -> applying (manual resume)
                         | -> failed -> ready_to_apply (bounded retry)
                         \ -> submitted -> interview -> offer
                                           \-> rejected
```

Every transition is validated and written to `application_status_history` with timestamp, actor, correlation ID, and reason. `submitted` does not return to `applying`.

### 8.3 Submission gates (future live submit)

All must pass before an irreversible submit click:

1. Env + DB policy allow submission (`APPLICATION_SUBMISSION_ENABLED`).
2. Daily limit / company allowlist OK.
3. Not already submitted locally or visibly confirmed remotely.
4. URL/title/company still match.
5. Eligibility/match evidence current enough (when matching exists).
6. Every required answer from verified fact or explicit user answer.
7. No CAPTCHA, pending OTP, consent, unknown, or validation error.
8. Preview hash matches user approval.
9. Short submission lease held.

MVP hard-codes gate 1 to false.

---

## 9. End-to-end workflows

### 9.1 Onboarding (MVP)

1. `terminal_hire` TUI → Onboard screen starts agent role `onboarder`.
2. Confirm **US job-search** scope for this profile.
3. Collect **core** facts: identity, contact, education, work, skills, US location/salary prefs, answer policies.
4. Ask which **work-auth packs** to enable (citizen / PR / other auth / OPT / STEM OPT / none extra). Skip irrelevant packs entirely.
5. Run only the question sets for enabled packs; save draft facts → user verifies.
6. Embed verified chunks if RAG enabled.
7. Resume screen: add `.tex` / build PDF.

### 9.2 Apply-by-URL dry-run (MVP primary)

1. Apply screen: paste URL → creates/links job + application (US market).
2. Playwright opens URL; stop on login/CAPTCHA/unexpected challenge.
3. Inventory fields; store snapshot; embed job text optionally.
4. `form_mapper` uses **core + enabled-pack facts only** (+ RAG); returns validated fill-plan JSON.
5. Fill/upload PDF only for approved mappings; never invent restricted/work-auth answers.
6. Preview report → `waiting_for_user_review` (Apps screen).
7. Apps screen: Approve / enter site OTP / Cancel as needed. (OTP = one-time code, not OPT.)
8. Stop before submit; prove no submit in tests.

Detail diagrams: [`FLOW.md`](./FLOW.md).

### 9.3 Future live application

1. Resume from approved dry-run when form fingerprint matches.
2. Re-map diffs; review changes.
3. Email OTP only via approved integration; SMS manual.
4. CAPTCHA → pause only (never solve/bypass).
5. Run gates → submit once → confirmation artifact → `submitted`.
6. Ambiguous click → human reconciliation, no blind retry.

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
| Onboard | Interview, verify, packs |
| Profile | Facts + packs |
| Resume | `.tex` → PDF |
| Apply | Paste US URL, dry-run |
| Apps | Preview, Approve, site OTP, Cancel, Resume |
| Settings | LLM switch, safety flags |

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
├─ src/terminal_hire/
│  ├─ __main__.py            # launch TUI
│  ├─ app.py                 # Textual App
│  ├─ tui/                   # screens only
│  ├─ config.py
│  ├─ db/
│  ├─ profile/
│  ├─ resume/
│  ├─ llm/
│  ├─ agent/
│  ├─ rag/
│  ├─ browser/
│  └─ apply/
├─ tests/
├─ fixtures/
└─ data/                     # gitignored
```

Future: `connectors/`, `matcher/`, optional script CLI — after MVP dry-run works.

---

## 13. Security and privacy

### 13.1 Data classification

- **Public:** job posts, public career URLs.
- **Internal:** scores (future), ops metadata, fill confidence.
- **Confidential:** resume content, history, application answers.
- **Restricted:** contact/address, immigration/work auth, OTP, demographics/disability/veteran, browser sessions, credentials.

### 13.2 Controls

- Local-first: prefer LM Studio for sensitive chat; treat OpenRouter as leaving the machine.
- Application-level encryption for restricted fields; keys not in Git.
- `.env` local only; never commit real keys.
- Redact logs; log ids/hashes/classes, not values.
- Sanitize stored HTML; strip scripts/tokens.
- SSRF caution when fetching URLs: block obvious local/metadata targets where practical; cap downloads.
- Validate resume files (type/size).
- Audit profile, policy, apply, OTP, approve, and future submit events.
- Export/delete path for profile + artifacts.

### 13.3 AI safety

- Send minimal redacted projection + form inventory, not the entire secret store.
- Schema-validate JSON plans; reject invalid plans.
- Treat page text as untrusted (prompt injection); cannot change tools, verified facts, or force submit.
- Model must not unilaterally answer work auth, immigration, salary, clearance, demographic, disability, veteran, employment dates, education credentials, or years-of-experience — those come from **verified core/pack facts** or explicit user input.
- Do not inject STEM OPT / H-1B framing into prompts when those packs are disabled.
- Pin provider + model id; record `model_runs` metadata (hashes, not raw secret prompts by default).

### 13.4 Artifacts & OTP

- Redact screenshots; strip secrets from HTML snapshots.
- OTP only in memory / short-TTL encrypted storage; delete after use/expiry; never log.
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

### 15.1 Unit

- Fact verification rules; state transitions; submission-gate invariants.
- JSON plan schema validation; redaction helpers.
- Resume compile dry path (mock or CI TeX where available).

### 15.2 LLM client

- Mock OpenAI-compatible server for lmstudio/openrouter shapes.
- Provider switch selects correct base URL/model.
- Invalid tool/JSON plans rejected.

### 15.3 Browser

- Local synthetic forms: text, select, checkbox, file upload, multi-step, OTP, CAPTCHA placeholder, confirmation.
- Intercept network: MVP cannot issue submit requests.
- Pause/resume, selector drift, crash recovery.

### 15.4 Acceptance (MVP)

- Onboard can create verified facts without leaking them in logs.
- LaTeX → PDF registered as document.
- `apply <url>` on synthetic page inventories fields and produces preview.
- CAPTCHA/unknown/OTP pause without automated bypass.
- Approve + OTP paths work in TUI Apps; submit remains disabled.
- Switching `LLM_PROVIDER` does not change DB schema or Playwright gates.

---

## 16. Deployment strategy

### 16.1 Local development (MVP)

- Python 3.11+ venv / uv; Playwright browsers installed locally.
- LM Studio running when `LLM_PROVIDER=lmstudio`; OpenRouter key when using cloud.
- SQLite + `data/` directory; no Docker required initially.
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
| **M0** | Decisions: default LLM provider, model ids, LaTeX engine, submit stays off | Choices recorded |
| **M1** | Python package, config, SQLite profile facts, `llm-check` / provider switch | Facts save/list/verify |
| **M2** | Agent runtime + `onboard` via LM Studio/OpenRouter | Profile from interview |
| **M3** | LaTeX → PDF | Uploadable resume |
| **M4** | Playwright URL inventory (no submit) | Fields stored from URL |
| **M5** | Form mapper + dry-run fill + approve | E2E dry-run on real pages |
| **M6** | OTP/CAPTCHA pause + resume | Interrupted applies recoverable |
| **M7** | Supervised submit (optional) | Explicit approve + flag |
| **M8** | ATS collectors, matching, email OTP, UI, scale-out | As needed |

Older TS/Postgres/dashboard-first milestones are **withdrawn** as the MVP path.

---

## 18. MVP versus future scope

### MVP

- Single user, one verified profile (TUI onboard).
- SQLite + files + optional Chroma.
- Python **Textual TUI** + agent (Grok Build–inspired) + LM Studio ↔ OpenRouter.
- LaTeX resume → PDF.
- URL-first Playwright dry-run; preview; OTP/CAPTCHA pause.
- No live submit; no CAPTCHA solve; no LinkedIn/Indeed scraping; no required cloud except optional OpenRouter.

### Future

- Greenhouse/Lever/Ashby (then more) collectors; eligibility evidence; scoring dashboard.
- Email OTP integration; supervised/autopilot submit if desired and permitted.
- Postgres, Redis, multi-process workers, hosted UI.
- Multiple profiles/users only if needed.

---

## 19. What should be built first

1. Config + SQLite profile facts + `llm-check` (both providers wired).
2. Agent runtime + onboard interview.
3. LaTeX → PDF.
4. `apply <url>` inventory only.
5. Mapper + dry-run fill + approve.
6. OTP/CAPTCHA resume paths.
7. Only then consider collectors/matching/UI/submit.

This matches URL-first product intent while keeping browser automation behind a working profile/LLM spine.

---

## 20. Unresolved technical and product decisions

| Decision | Options | Recommendation for now |
|---|---|---|
| Default `LLM_PROVIDER` | lmstudio; openrouter; off | `lmstudio` for private onboard; OpenRouter when local quality is weak |
| LM Studio model | user-loaded id | Prefer a model decent at JSON / tools |
| OpenRouter model | catalog slug | Start with a mid-cost strong JSON model; pin id |
| Embeddings | LM Studio; fastembed local; OpenRouter | **Local** (`fastembed` or LM Studio) even if chat is OpenRouter |
| Package/tooling | uv; poetry; pip | `uv` or plain `pyproject.toml` + pip |
| ORM | SQLModel; SQLAlchemy; raw SQL | SQLModel/SQLAlchemy |
| LaTeX engine | tectonic; MiKTeX; TeX Live | Whatever is installed; document in README |
| Vector DB | Chroma; LanceDB; none until M5 | Chroma after onboard works; optional until mapper needs it |
| Submission consent | Per-job; allowlist autopilot | Per-job approve for first live release |
| Browser profile | Persistent encrypted; ephemeral | Ephemeral first; persistent later if logins required |
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
- No live submit until MVP dry-run acceptance passes and user enables policy.

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

This document, `SYSTEM_ARCHITECTURE.md`, and `FLOW.md` together are the planning baseline (not legal approval). Stack, **TUI**, LLM switch, and milestone order are aligned on the Python URL-first MVP. Before coding M1, resolve §20 items that affect config (default provider, model ids, LaTeX). Material deviations should be recorded (short ADR under `docs/adr/`), and README / `.env.example` must stay consistent.

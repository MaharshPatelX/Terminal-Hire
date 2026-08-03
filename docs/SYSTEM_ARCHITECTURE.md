# Terminal-Hire — System Architecture (Python + Local LLM)

Status: target implementation blueprint; current code status is tracked separately
Language: **Python only**  
Target LLM: **LM Studio (local)** and/or **OpenRouter**, switchable through an OpenAI-compatible interface
Target agent runtime: **project-owned Python services** with explicit tools and permission gates
Last updated: 2026-08-02

This document is the **active build blueprint** (modules, **TUI**, LLM switch, M0–M8).  
[`PROJECT.md`](./PROJECT.md) is the aligned **full product/requirements plan** (US scope, profile packs, data model, safety, MVP vs future).  
[`FLOW.md`](./FLOW.md) is the **end-to-end TUI + system flow map**.  
[`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) is the **code-backed current-state and gap audit**.
Docs index: [`README.md`](./README.md). Root summary: [`../README.md`](../README.md).  
If docs disagree on current behavior, `IMPLEMENTATION_STATUS.md` wins. This file wins for target stack and milestone order.

---

## 1. Product in one sentence

**Terminal-Hire** aims to be a local Python **TUI** for **supervised US job applications**: it stores verified facts and documents, takes a career-page URL, fills through Playwright, and requires review before an optional one-use Submit click. Agentic mapping, dual-provider inference, full pack behavior, and LaTeX resume generation are target capabilities, not current ones.

---

## 2. Design principles

1. **Start from apply-by-URL** for **US** career pages — not ATS board crawling.
2. **Python owns the product** — **TUI**, DB, Playwright, RAG, **and the agent loop**.
3. **TUI-first UX** — Textual fullscreen app; business logic in services (not in widgets).
4. **The agent runtime is project-owned** — explicit tools, typed plans, and permission gates.
5. **Inference is OpenAI-standard and pluggable** — `LLM_PROVIDER=lmstudio|openrouter|off`.
6. **Playwright owns the browser** — model proposes; Python executes under gates.
7. **`PROFILE.md` is profile truth** — strict fields plus readable professional narrative and portal Q&A.
8. **Profile packs** — core US apply for everyone; STEM OPT / H-1B / etc. only if enabled.
9. **Deterministic before Agentic RAG** — exact local fields, then non-sensitive retrieval, then ask.
10. **SQLite is application memory** — plaintext site credentials by explicit policy, events, checkpoints, and evidence.
11. **Supervised submit only** — disabled by default, exact preview approval, one-use click, no blind retry.
12. **Never fabricate** work history, work-auth, salary, or demographics.

---

## 3. High-level architecture

Target architecture. The general Apply agent and dual-provider blocks are planned; the TUI, deterministic services, SQLite store, OpenRouter health check/private onboarding, and generic Playwright worker exist today. Apply/form-mapping inference is not implemented.

```text
┌─────────────────────────────────────────────────────────────┐
│              Python TUI (Textual) — primary UI               │
│ First run: Onboard | Ready: Profile | Apply | Apps | Settings│
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                v                             v
┌───────────────────────────┐   ┌─────────────────────────────┐
│  Our Agent Runtime        │   │   Apply Orchestrator        │
│  (typed plans + tools)    │   │   (state machine + gates)   │
│                           │   │                             │
│  • message / tool loop    │   │  1. open URL (Playwright)   │
│  • tool registry          │◄──┤  2. inventory fields        │
│  • permission gates       │   │  3. ask agent for mapping   │
│  • onboarder / mapper     │   │  4. fill from verified facts│
│  • coach roles            │   │  5. pause OTP/CAPTCHA/ask   │
└─────────────┬─────────────┘   │  6. preview → approve       │
              │                 │  7. one-use submit gate     │
              │                 └──────────────┬──────────────┘
              v                                v
┌───────────────────────────┐   ┌─────────────────────────────┐
│  LLM providers (switch)   │   │  Playwright browser worker  │
│  LM Studio  OR OpenRouter │   │  artifacts / checkpoints    │
│  both OpenAI-compatible   │   └─────────────────────────────┘
│  LLM_PROVIDER=...         │
└───────────────────────────┘
              │
              v
┌───────────────────────────┐
│  Local data plane         │
│ PROFILE.md · SQLite · files│
└───────────────────────────┘
```

Full screen-by-screen flows: [`FLOW.md`](./FLOW.md).

### 3.1 Project-owned agent runtime

This is the target runtime. None of the `agent/` modules below exist in the audited baseline:

| Capability | Python implementation |
|---|---|
| Agent loop (context → model → tools → repeat) | `agent/runtime.py` |
| Tool definitions + dispatch | `agent/tools/` registry |
| Permissions before dangerous actions | allowlists; never auto-submit |
| Agent role files (prompt + tools) | `agent/roles/*.md` |
| Multi-turn session | conversation state + SQLite run log |
| Clear separation host vs model | orchestrator + LLM client |

### 3.2 Dual providers: LM Studio ↔ OpenRouter (same OpenAI client)

This is the target provider design. Current code has an OpenRouter client, Settings health check, JSON chat, a separate DeepSeek model, and OpenRouter automatic provider routing for onboarding. There is still no shared provider factory, LM Studio adapter, or Apply/form-mapping integration.

| Provider | When to use | Base URL | Key |
|---|---|---|---|
| `lmstudio` | Local, private, free runtime | `http://localhost:1234/v1` | any placeholder (e.g. `lm-studio`) |
| `openrouter` | Cloud models, stronger tool/JSON quality | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| `off` | No LLM calls (manual facts / inventory only) | — | — |

**Switch rules:**

- Exactly **one active chat provider** at a time (`LLM_PROVIDER`).
- You can keep **both configs filled** in `.env` and flip the switch without rewriting code.
- TUI Settings shows the provider in memory. Only OpenRouter has a working health check; changing the provider is not persisted.
- Optional later: `--provider` override for scripted runs that call the same services.

Proposed factory shape (not current code):

```python
from openai import OpenAI

def make_llm_client(settings) -> OpenAI | None:
    if settings.llm_provider == "off":
        return None
    if settings.llm_provider == "lmstudio":
        return OpenAI(
            base_url=settings.lmstudio_base_url,  # http://localhost:1234/v1
            api_key=settings.lmstudio_api_key or "lm-studio",
        )
    if settings.llm_provider == "openrouter":
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            default_headers={
                # Recommended by OpenRouter for rankings/apps
                "HTTP-Referer": settings.openrouter_http_referer or "http://localhost",
                "X-Title": settings.openrouter_app_title or "Terminal-Hire",
            },
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")

# then:
# client.chat.completions.create(model=settings.active_model, messages=[...], tools=[...])
```

**Model ids:**

- LM Studio: id shown in the local server UI for the loaded model.
- OpenRouter: slug like `openai/gpt-4.1-mini` or `anthropic/claude-sonnet-4` (whatever you pick in their catalog).

**Privacy note:** with `lmstudio`, selected context stays on your machine. With `openrouter`, selected context leaves the machine. Never send the full profile, SSN/document values, passwords, OTPs, or raw restricted answers; only minimal non-sensitive chunks may enter model context.

**Tool-calling strategy:**

1. Prefer native OpenAI `tools` / `tool_calls` when the active model handles them well (often better on OpenRouter).
2. If not, **JSON-plan fallback** — same for both providers.

---

## 4. User journey (main flow)

### Phase A — First-time setup

Target flow:

```text
terminal-hire                    # missing/incomplete PROFILE.md → Onboard

Confirm US job-search scope.
Collect CORE facts, professional history, optional SSN/document numbers, documents, and policies.
Ask which work-auth PACKS to enable (citizen / PR / other / OPT / STEM OPT / …).
Ask pack-specific questions ONLY for enabled packs.

Each answer → atomic PROFILE.md draft → user reviews → types VERIFY
Returning launch → Profile | Apply | Applications | Settings
```

See `PROJECT.md` §3.1 for pack list. STEM OPT caution applies only if that pack is on.
OTP on career sites = one-time code (core apply) — not the same as OPT.

Current onboarding uses staged local validation, local review, optional AI phrasing/redacted professional review, and local fallback. It does not collect SSN/passport/license data. Pack flags are still selected later in Profile and do not trigger pack-specific questions or mapping gates.

### Phase B — Apply from career URL

```text
TUI → Apply screen → paste URL → Start audited application

1. Snapshot PROFILE.md hash and create SQLite application row
2. Playwright opens URL; saved site credentials support login/account creation
3. Pause for consent, CAPTCHA, or site OTP
4. Inventory fields
5. Resolve exact profile fields → reusable Q&A/search → minimal agent context → ask user
6. Fill one field at a time; save events, confidence, screenshots, and checkpoints
7. Preview values + sources + evidence on Applications screen
8. User approves the exact preview hash
9. If enabled, atomically consume approval and click Submit once
10. Capture confirmation; ambiguous result stops without retry
```

Detail: [`FLOW.md`](./FLOW.md).
---

## 5. Modules (Python package layout)

```text
Terminal-Hire/
  pyproject.toml
  docs/                           # FLOW, SYSTEM_ARCHITECTURE, PROJECT
  src/
    __main__.py                       # launches TUI by default
    app.py                            # Textual App
    tui/                              # screens & widgets only
      home.py
      onboard.py
      profile.py
      apply.py
      apps.py
      settings.py
    config.py                         # pydantic-settings
    profile/                          # PROFILE.md model/repository/retrieval
    db/                               # credentials + application audit
    browser/                          # Playwright + artifacts + submit click
    apply/                            # profile-backed orchestration + gates
  tests/
```

Runtime files are not kept under the repository. Windows defaults to `%LOCALAPPDATA%\TUI-Hire`.

Optional thin CLI (`typer`) may wrap the same services for scripting; **TUI is the product UI**.

---

## 6. Local data model

### `PROFILE.md`

The only profile source of truth: metadata, identity/contact, sensitive identity, location, professional summary, education, work history, projects, skills, work authorization/packs, documents, common answers, portal Q&A, policies, insights, verification, and provenance.

Strict YAML front matter is machine-authoritative; the Markdown body is a readable rendering. Writes validate, replace atomically, and retain one backup.

### SQLite

| Table | Purpose |
|---|---|
| `credentials` | Domain account + plaintext password by explicit policy |
| `runtime_settings` | Persist local submit-policy switch |
| `applications` | URL, status, PROFILE.md hash, preview hash |
| `application_events` | Ordered redacted audit trail |
| `field_actions` | Value/hash, source, confidence, sensitivity, result |
| `browser_checkpoints` | Resume step, URL, safe state JSON |
| `artifacts` | Redacted screenshot/evidence paths |
| `submit_approvals` | Preview-bound one-use approval |

Observed statuses include `ready_to_apply`, `applying`, `waiting_for_credential`, `waiting_for_user_answer`, `waiting_for_otp`, `waiting_for_consent`, `blocked_by_captcha`, `waiting_for_user_review`, `approved`, `submitting`, `submitted`, `submission_uncertain`, and `cancelled`. They are currently free-form strings; transition validation and a dedicated status-history table are planned.

---

## 7. Agent runtime design

This entire section is planned. Current retrieval is deterministic/lexical and asks the user when it cannot resolve a field.

### 7.1 Loop (simplified)

```text
load role (system prompt + allowed tools)
while turns < max:
  call LM Studio chat.completions (OpenAI API)
  if assistant wants tools:
     check permission allowlist
     execute tool in Python
     append tool result
  elif assistant returns final JSON / question to user:
     validate + return to orchestrator/CLI
```

### 7.2 Roles

| Role | Job | Tools |
|---|---|---|
| `onboarder` | Interview → PROFILE.md draft | save_profile_draft, read_profile |
| `form_mapper` | Inventory → fill plan JSON | exact_profile_lookup, profile_search (read-only) |
| `coach` | Explain blockers | read-only |

### 7.3 Contract with Playwright

Agent returns plans; Python executes:

```json
{
  "actions": [
    {"op": "fill", "field_id": "email", "from_fact": "contact.email"},
    {"op": "upload", "field_id": "resume", "document_tag": "primary_pdf"},
    {"op": "ask_user", "field_id": "visa_status", "reason": "no verified fact"},
    {"op": "pause", "reason": "otp_detected"}
  ],
  "confidence": 0.82,
  "notes": ["Salary left blank per policy"]
}
```

Invalid JSON → reject; do not fill.

---

## 8. Browser / “any career page”

Best-effort, not magic:

1. Generic DOM field inventory is implemented
2. Known-ATS detection and adapters are planned
3. Saved credentials fill login/account fields; consent and CAPTCHA pause
4. Resume/document path comes from PROFILE.md
5. OTP pauses for TUI entry and is never persisted
6. Filled fields record an event and redacted screenshot; checkpoints exist for open/inventory, not every fill

Browser contexts are ephemeral and checkpoints are not loaded for restart recovery.

---

## 9. RAG (local)

Planned. `ProfileRetriever.safe_context` currently ranks non-sensitive chunks lexically, but no workflow consumes those chunks and no vector index exists.

- Index only non-sensitive verified professional chunks and portal Q&A
- The index is disposable and rebuilt from PROFILE.md
- Exact PROFILE.md fields win; SSN/document numbers never enter RAG or cloud prompts

---

## 10. Safety gates

Target gates:

1. Submission setting explicitly enabled
2. Required fields from verified profile data or explicit user answers only
3. No open CAPTCHA / unknown / consent  
4. OTP done if required  
5. Preview hash matches approval  
6. Approval atomically claimed once before click
7. URL still matches; ambiguous result is never retried

No CAPTCHA bypass. Password/OTP/sensitive identity values are redacted from logs and screenshots.

Current submit code enforces the enable switch, stored preview approval, one-use claim, active session, and exactly one Submit control. It does **not** yet revalidate current profile hash, live DOM/required fields, blockers, or current URL/domain immediately before click. See the P0 audit findings before enabling Submit.

---

## 11. TUI surface (MVP)

Primary app screens (see [`FLOW.md`](./FLOW.md) for full flows):

| Screen | Actions |
|---|---|
| Onboard | Forced first-run interview, atomic drafts, review, verify |
| Home | Ready-state launchpad and readiness |
| Profile | All details, SSN/docs, history, packs, documents, reusable Q&A |
| Apply | URL, credentials, OTP, field retrieval, audited browser fill |
| Applications | Values/sources/evidence, approve, one supervised Submit click |
| Settings | LLM provider, OS-local paths, submit policy |

Entry: `terminal-hire` or `python -m src` → Textual TUI.
Optional later: scripted service calls for automation — not required for MVP.
---

## 12. Config (`.env` sketch)

Only settings loaded by the committed `Settings` model are shown here. Roadmap knobs must not be treated as active until code loads and enforces them.

```text
APPLICATION_DRY_RUN=true
APPLICATION_SUBMISSION_ENABLED=false

# Defaults outside repository/OneDrive:
# DATA_DIR=C:\Users\you\AppData\Local\TUI-Hire
PROFILE_FILENAME=PROFILE.md
DATABASE_FILENAME=terminal_hire.sqlite
ARTIFACT_DIRNAME=artifacts
APP_TIMEZONE=America/Chicago

# Which brain is on: lmstudio | openrouter | off
LLM_PROVIDER=lmstudio

# --- OpenRouter (cloud OpenAI-compatible) ---
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=qwen/qwen3.6-35b-a3b
OPENROUTER_PROVIDER=venice
OPENROUTER_ALLOW_FALLBACKS=false
OPENROUTER_HTTP_REFERER=https://github.com/MaharshPatelX/Terminal-Hire
OPENROUTER_APP_TITLE=Terminal-Hire
OPENROUTER_TIMEOUT_SECONDS=60

# Private onboarding:
ONBOARDING_AI_ENABLED=true
ONBOARDING_AI_MODEL=deepseek/deepseek-v4-flash
ONBOARDING_AI_MAX_REVIEW_ROUNDS=3

PLAYWRIGHT_HEADLESS=false
```

**How on/off works:**

- `LLM_PROVIDER` accepts `lmstudio`, `openrouter`, or `off`, but only the OpenRouter Settings health check is implemented.
- OpenRouter is validated when its client is constructed, not at application startup.
- The Settings provider choice is in-memory only. The supervised-submit switch is persisted in SQLite.
- `APPLICATION_DRY_RUN` is loaded but does not currently control the browser or submit gate.
- Private onboarding sends field-status metadata and pattern-redacted professional text through OpenRouter automatic provider routing when enabled; it does not use the configured Venice-only route.

Planned/not loaded: LM Studio settings, daily limits, shared agent tuning, concurrency, email OTP, logging level, and retention settings.

---

## 13. Build milestones

### M0 — Textual shell and decisions (implemented)

### M1 — PROFILE.md + onboarding (foundation implemented)

- Strict model/parser, readable rendering, atomic write, backup recovery, hash
- Forced first-run onboarding, four-item ready navigation, profile/Q&A editor
- Deterministic exact and lexical retrieval with sensitive-context exclusion
- Semantic local validation plus redacted OpenRouter-assisted onboarding

### M2 — SQLite application audit + supervised apply (experimental foundation)

- Plaintext site credentials by explicit policy, events, field actions, checkpoints, artifacts
- Playwright login/account/OTP/inventory/fill and screenshot evidence
- Preview hash, one-use approval, one-click supervised submit

### M3 — LaTeX → PDF  

### M4 — Harden Playwright with ATS/synthetic fixtures

### M5 — OpenAI-compatible agent + disposable non-sensitive RAG (OpenRouter onboarding only)

### M6 — Browser restart recovery + ATS adapters

### M7 — Supervised-submit security/soak hardening

### M8 — ATS collectors, email OTP, etc.  

---

## 14. Build first this week

1. Add submit-time profile/live-page/blocker/URL checks, status transitions, and daily limits
2. Expand synthetic browser fixtures and add restart recovery
3. Strengthen onboarding free-text redaction/cloud-consent UX, then integrate a schema-validated mapper
4. Decide whether LM Studio and vector retrieval are still required; implement them if retained
5. Add real pack schemas plus LaTeX/PDF document validation, build, and hashing

---

## 15. Relationship to `PROJECT.md`

All docs were reconciled on 2026-08-02. Current-state detail lives in `IMPLEMENTATION_STATUS.md`:

| Doc | Role |
|---|---|
| `SYSTEM_ARCHITECTURE.md` | Build blueprint: packages, **TUI**, LLM switch, M0–M8 |
| `FLOW.md` | End-to-end TUI + apply flows |
| `PROJECT.md` | Full requirements: US scope, profile packs, data model, safety, MVP vs future |
| `IMPLEMENTATION_STATUS.md` | Code-backed status, risks, configuration truth, and test coverage |

Shared decisions: Python, URL-first flow, PROFILE.md truth, SQLite application audit, plaintext local credentials, deterministic-before-RAG retrieval, supervised one-use submit, and OTP/CAPTCHA/consent pauses.

---

## 16. Open decisions

1. Keep `lmstudio` as the default before its adapter exists, or default to `off`?
2. Retain LM Studio in MVP? If yes, which chat model id?
3. Embeddings: LM Studio vs `fastembed`?  
4. Default work-auth packs at onboard (usually none until user picks)?  
5. LaTeX engine on your PC?  
6. Headful Playwright while developing?  
7. Retention period for application screenshots and events?

---

## 17. Implemented foundation

- URL-first Textual TUI with forced onboarding and four ready-state screens
- PROFILE.md source of truth with recovery and deterministic retrieval
- SQLite application/credential/audit storage
- Playwright worker with redacted evidence and human blockers
- Preview-bound, one-use supervised-submit gate
- Standalone OpenRouter client plus Settings connection check
- 28 automated profile, storage, browser, LLM-client, submit-gate, and TUI routing tests

Private onboarding is merged in the audited base. The full suite has 43 passing tests.

This foundation is not a production-readiness statement. See `IMPLEMENTATION_STATUS.md` for missing submit-time checks and test gaps.

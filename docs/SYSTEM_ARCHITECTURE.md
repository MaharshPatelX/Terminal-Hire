# Terminal-Hire — System Architecture (Python + Local LLM)

Status: planning  
Language: **Python only**  
LLM: **LM Studio (local)** and/or **OpenRouter** — both via **OpenAI-compatible API**, switchable  
Agent design reference: **Grok Build** (open-source patterns only — **not** a runtime dependency)  
Last updated: 2026-07-26

This document is the **active build blueprint** (modules, **TUI**, LLM switch, M0–M8).  
[`PROJECT.md`](./PROJECT.md) is the aligned **full product/requirements plan** (US scope, profile packs, data model, safety, MVP vs future).  
[`FLOW.md`](./FLOW.md) is the **end-to-end TUI + system flow map**.  
Docs index: [`README.md`](./README.md). Root summary: [`../README.md`](../README.md).  
If docs disagree on stack or MVP order, update both — this file wins for implementation detail until reconciled.

---

## 1. Product in one sentence

**Terminal-Hire** is a local Python **TUI** for **US job applications**: interviews you, stores verified facts + a LaTeX resume (plus **optional work-auth packs** like citizen / OPT / STEM OPT only if you enable them), then takes a US career-page URL and uses **your own agent runtime** (Grok Build–inspired) with **LM Studio or OpenRouter**, plus Playwright, to fill applications safely (preview first; submit only when allowed).

---

## 2. Design principles

1. **Start from apply-by-URL** for **US** career pages — not ATS board crawling.
2. **Python owns the product** — **TUI**, DB, Playwright, RAG, **and the agent loop**.
3. **TUI-first UX** — Textual fullscreen app; business logic in services (not in widgets).
4. **Grok Build is a blueprint, not a dependency**.
5. **Inference is OpenAI-standard and pluggable** — `LLM_PROVIDER=lmstudio|openrouter|off`.
6. **Playwright owns the browser** — model proposes; Python executes under gates.
7. **Facts are structured; RAG is search** — SQLite wins; vectors never invent facts.
8. **Profile packs** — core US apply for everyone; STEM OPT / H-1B / etc. only if enabled.
9. **Dry-run by default** — pause on site OTP / CAPTCHA / unknown (OTP ≠ OPT).
10. **Never fabricate** work history, work-auth, salary, or demographics.

---

## 3. High-level architecture

```text
┌─────────────────────────────────────────────────────────────┐
│              Python TUI (Textual) — primary UI               │
│  Home | Onboard | Profile | Resume | Apply | Apps | Settings│
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                v                             v
┌───────────────────────────┐   ┌─────────────────────────────┐
│  Our Agent Runtime        │   │   Apply Orchestrator        │
│  (Grok Build–inspired)    │   │   (state machine + gates)   │
│                           │   │                             │
│  • message / tool loop    │   │  1. open URL (Playwright)   │
│  • tool registry          │◄──┤  2. inventory fields        │
│  • permission gates       │   │  3. ask agent for mapping   │
│  • onboarder / mapper     │   │  4. fill from verified facts│
│  • coach roles            │   │  5. pause OTP/CAPTCHA/ask   │
└─────────────┬─────────────┘   │  6. preview → approve       │
              │                 │  7. submit (future flag)    │
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
│  SQLite · files · Chroma  │
└───────────────────────────┘
```

Full screen-by-screen flows: [`FLOW.md`](./FLOW.md).

### 3.1 Grok Build = reference only

Study your local tree `coding-agent/grok-build` (and the public repo) for **structure**, then reimplement the useful parts in Python:

| Borrow from Grok Build | Our Python equivalent |
|---|---|
| Agent loop (context → model → tools → repeat) | `agent/runtime.py` |
| Tool definitions + dispatch | `agent/tools/` registry |
| Permissions before dangerous actions | allowlists; never auto-submit |
| Agent role files (prompt + tools) | `agent/roles/*.md` |
| Multi-turn session | conversation state + SQLite run log |
| Clear separation host vs model | orchestrator + LLM client |

| Do **not** require at runtime | Why |
|---|---|
| `grok` CLI / TUI | You want LM Studio, not that harness |
| `xg-agent-sdk` | Optional reading only |
| `XAI_API_KEY` / cloud Grok | Inference stays local |

### 3.2 Dual providers: LM Studio ↔ OpenRouter (same OpenAI client)

Both speak OpenAI-compatible chat completions. Python uses **one** `OpenAI` client factory; only `base_url`, `api_key`, and `model` change.

| Provider | When to use | Base URL | Key |
|---|---|---|---|
| `lmstudio` | Local, private, free runtime | `http://localhost:1234/v1` | any placeholder (e.g. `lm-studio`) |
| `openrouter` | Cloud models, stronger tool/JSON quality | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| `off` | No LLM calls (manual facts / inventory only) | — | — |

**Switch rules:**

- Exactly **one active chat provider** at a time (`LLM_PROVIDER`).
- You can keep **both configs filled** in `.env` and flip the switch without rewriting code.
- TUI Settings / health panel reports which provider is active and whether the OpenAI-compatible endpoint responds.
- Optional later: `--provider` override for scripted runs that call the same services.

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

**Privacy note:** with `lmstudio`, profile text stays on your machine. with `openrouter`, prompts/facts you send leave your machine — still redact secrets in logs; avoid sending full resume blobs unless needed.

**Tool-calling strategy:**

1. Prefer native OpenAI `tools` / `tool_calls` when the active model handles them well (often better on OpenRouter).
2. If not, **JSON-plan fallback** — same for both providers.

---

## 4. User journey (main flow)

### Phase A — First-time setup

```text
python -m terminal_hire          # opens TUI → Onboard screen

Confirm US job-search scope.
Collect CORE facts (identity, contact, education, work, skills, US location, salary, policies).
Ask which work-auth PACKS to enable (citizen / PR / other / OPT / STEM OPT / …).
Ask pack-specific questions ONLY for enabled packs.

Each answer → draft fact in SQLite → you verify → embed to Chroma if enabled

Resume screen → store .tex → compile PDF → register document
```

See `PROJECT.md` §3.1 for pack list. STEM OPT caution applies only if that pack is on.
OTP on career sites = one-time code (core apply) — not the same as OPT.

### Phase B — Apply from career URL

```text
TUI → Apply screen → paste URL → Start dry-run

1. Create application row
2. Playwright opens URL
3. Detect ATS vs generic form vs login/CAPTCHA blocker
4. Save job text + field inventory; embed job
5. Agent mapper gets inventory + core + enabled-pack facts (+ RAG)
   → returns fill plan JSON
6. Orchestrator fills only verified / policy-approved values
7. Preview on Apps screen → waiting_for_user_review
8. User Approve
9. Site OTP (one-time code) → waiting_for_otp → enter code in TUI
10. Submit only if APPLICATION_SUBMISSION_ENABLED=true
```

Detail: [`FLOW.md`](./FLOW.md).
---

## 5. Modules (Python package layout)

```text
terminal_hire/
  pyproject.toml
  docs/                           # FLOW, SYSTEM_ARCHITECTURE, PROJECT
  src/terminal_hire/
    __main__.py                       # launches TUI by default
    app.py                            # Textual App
    tui/                              # screens & widgets only
      home.py
      onboard.py
      profile.py
      resume.py
      apply.py
      apps.py
      settings.py
    config.py                         # pydantic-settings
    db/                               # SQLite models/repos
    profile/                          # facts, packs, verify, policies
    resume/                           # LaTeX → PDF
    rag/                              # Chroma + embeddings
    llm/
      openai_client.py                # OpenAI SDK factory → LM Studio or OpenRouter
      providers.py
      schemas.py
    agent/
      runtime.py
      permissions.py
      roles/
      tools/
    browser/
    apply/                            # orchestrator + gates
  data/
  tests/
```

Optional thin CLI (`typer`) may wrap the same services for scripting; **TUI is the product UI**.

---

## 6. Data model (SQLite first)

| Table | Purpose |
|---|---|
| `profile` | Single-user metadata + `enabled_packs` + market=`US` |
| `profile_facts` | Versioned facts + verification (+ optional `pack_id`) |
| `answer_policies` | e.g. demographics = decline |
| `documents` | `.tex` + PDF paths |
| `jobs` | URL, title, company, raw text |
| `applications` | status, preview hash |
| `application_events` | audit |
| `form_snapshots` | field inventory JSON |
| `field_mappings` | agent plan + results |
| `blockers` | OTP, CAPTCHA, unknown, consent |

Statuses: `ready_to_apply` → `applying` → `waiting_for_user_review` | `waiting_for_otp` | `blocked_by_captcha` | `failed` → `submitted` (future).

---

## 7. Agent runtime design (ours, Grok-inspired)

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
| `onboarder` | Interview → structured facts | save_draft_fact, list_facts |
| `form_mapper` | Inventory → fill plan JSON | get_facts, rag_search (read-only) |
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

1. Detect known ATS when possible  
2. Else generic DOM field inventory  
3. Login / CAPTCHA → hard pause (never bypass)  
4. Resume = compiled PDF from LaTeX  
5. OTP = pause + CLI `otp` command; SMS always manual  

---

## 9. RAG (local)

- Embed verified profile chunks, job text, past Q&A  
- Chroma (or LanceDB) + local embeddings (LM Studio embeddings endpoint **or** `fastembed`)  
- RAG feeds the mapper as context; **exact SQLite facts win** for email/phone/dates/immigration  

---

## 10. Safety gates

1. Dry-run / submit flag off → stop after preview  
2. Required fields from verified facts or explicit user answers only  
3. No open CAPTCHA / unknown / consent  
4. OTP done if required  
5. Preview hash matches approval  
6. Daily limit  
7. URL still matches  

No CAPTCHA bypass. Redact secrets from logs/screenshots.

---

## 11. TUI surface (MVP)

Primary app screens (see [`FLOW.md`](./FLOW.md) for full flows):

| Screen | Actions |
|---|---|
| Home | Readiness, recent apps, blockers |
| Onboard | Agent interview, verify facts, pick packs |
| Profile | Facts + enable/disable packs |
| Resume | Add `.tex`, build PDF |
| Apply | Paste URL, start dry-run, live progress |
| Apps | Status list, preview, Approve, enter site OTP, Cancel, Resume |
| Settings | LLM provider switch, models, dry-run/submit flags, paths |

Entry: `python -m terminal_hire` → Textual TUI.  
Optional later: scripted service calls for automation — not required for MVP.
---

## 12. Config (`.env` sketch)

```text
APPLICATION_DRY_RUN=true
APPLICATION_SUBMISSION_ENABLED=false
APPLICATION_DAILY_LIMIT=5

DATABASE_URL=sqlite:///./data/terminal_hire.sqlite
CHROMA_PATH=./data/chroma
RESUME_DIR=./data/resumes
ARTIFACT_DIR=./data/artifacts

# Which brain is on: lmstudio | openrouter | off
LLM_PROVIDER=lmstudio

# --- LM Studio (local OpenAI-compatible) ---
LMSTUDIO_ENABLED=true
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=lm-studio
LMSTUDIO_MODEL=local-model-id-from-lm-studio
# Optional local embeddings via LM Studio
LMSTUDIO_EMBEDDING_MODEL=

# --- OpenRouter (cloud OpenAI-compatible) ---
OPENROUTER_ENABLED=true
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4.1-mini
OPENROUTER_HTTP_REFERER=http://localhost
OPENROUTER_APP_TITLE=Terminal-Hire

# Shared LLM behavior
LLM_JSON_PLAN_FALLBACK=true
LLM_TEMPERATURE=0.2
LLM_MAX_TURNS=20

PLAYWRIGHT_HEADLESS=false
EMAIL_OTP_ENABLED=false
```

**How on/off works:**

- `LLM_PROVIDER` selects the active chat backend (`lmstudio`, `openrouter`, or `off`).
- `LMSTUDIO_ENABLED` / `OPENROUTER_ENABLED` are soft gates: if you set `LLM_PROVIDER=openrouter` but `OPENROUTER_ENABLED=false` (or missing key), startup/`llm-check` fails clearly instead of silently calling the wrong host.
- Both can stay `ENABLED=true` with keys/URLs filled; you only flip `LLM_PROVIDER` (or use the CLI helper) to switch.

---

## 13. Build milestones

### M0 — Decisions

- Default provider: LM Studio vs OpenRouter for day-to-day  
- LM Studio model id (local) and/or OpenRouter model slug  
- Confirm LaTeX toolchain on Windows  
- Submit stays disabled  

### M1 — Skeleton + profile store

- Package, Textual app shell, SQLite, config with `LLM_PROVIDER` + both provider blocks  
- Settings screen: provider switch + connection check  
- Manual fact save/list/verify in Profile  

### M2 — Our agent runtime + onboard

- Minimal Grok-inspired loop + OpenAI client factory (LM Studio **or** OpenRouter)  
- Onboard **TUI screen** interview → draft facts → verify + packs  
- Optional Chroma embed  

### M3 — LaTeX → PDF  

### M4 — Playwright URL inventory (no submit)  

### M5 — Form mapper + dry-run fill + approve  

### M6 — OTP / CAPTCHA pause + resume  

### M7 — Supervised submit (optional)  

### M8 — ATS collectors, email OTP, etc.  

---

## 14. Build first this week

1. Python + Textual shell + SQLite profile  
2. OpenAI client factory → LM Studio **and** OpenRouter (Settings check)  
3. Tiny agent loop + Onboard screen  
4. Apply screen URL inventory only  

---

## 15. Relationship to `PROJECT.md`

Both docs are aligned (2026-07-26):

| Doc | Role |
|---|---|
| `SYSTEM_ARCHITECTURE.md` | Build blueprint: packages, **TUI**, LLM switch, M0–M8 |
| `FLOW.md` | End-to-end TUI + apply flows |
| `PROJECT.md` | Full requirements: US scope, profile packs, data model, safety, MVP vs future |

Shared decisions: Python, URL-first MVP, SQLite, Grok Build as reference only, LM Studio ↔ OpenRouter, dry-run/OTP/CAPTCHA rules.

---

## 16. Open decisions

1. Default `LLM_PROVIDER`: `lmstudio` or `openrouter`?  
2. LM Studio chat model id? OpenRouter model slug?  
3. Embeddings: LM Studio vs `fastembed`?  
4. Default work-auth packs at onboard (usually none until user picks)?  
5. LaTeX engine on your PC?  
6. Headful Playwright while developing?  
7. Always per-application approve for submit?  

---

## 17. Done enough to code when we agree

- URL-first flow + **Textual TUI**  
- **Own Python agent** inspired by Grok Build  
- **LM Studio + OpenRouter**, same OpenAI client, `LLM_PROVIDER` switch  
- SQLite + optional Chroma  
- Milestone order M1→M5  
- Flows documented in `FLOW.md`  

Then start M1 in a coding chat (this chat can stay planning until you say go).

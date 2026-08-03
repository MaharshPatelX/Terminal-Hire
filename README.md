# Terminal-Hire

**Hire from the terminal.** A local Python TUI prototype for **supervised US job applications**: build one verified `PROFILE.md`, reuse answers learned from job portals, fill generic forms with Playwright, capture an audit trail, and gate one supervised Submit click behind review.

Supervised submit is implemented as a tested foundation and is **off by default**. It is not production-ready; see the [implementation audit](./docs/IMPLEMENTATION_STATUS.md) before enabling it.

## Status

| Area | State |
|---|---|
| Textual TUI and routing | Implemented |
| Markdown profile + reusable Q&A | Implemented foundation |
| Private-AI onboarding + profile editor | Implemented foundation |
| SQLite credentials / application audit | Implemented foundation |
| Generic Playwright inventory/fill/evidence | Experimental foundation |
| Supervised submit gate | Experimental; opt-in and one-use |
| OpenRouter client | Settings health check + private onboarding; not used by Apply |
| LM Studio / agent / vector RAG | Planned |
| ATS adapters / restart recovery / resume build | Planned |

Status was audited against `origin/main` at merge commit `f4176c7` on 2026-08-02. All 43 tests pass.

## Quick start

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/MaharshPatelX/Terminal-Hire.git
cd Terminal-Hire
uv sync
uv run playwright install chromium
cp .env.example .env   # optional; edit LLM settings later
uv run terminal-hire
```

Alternate launch:

```powershell
uv run python -m src
```

### Keyboard

| Key | Action |
|---|---|
| `1`–`4` | Profile / Apply / Applications / Settings |
| `↑` `↓` `Enter` | Move welcome menu / open |
| `esc` | Home |
| `ctrl+q` | Quit |
| `/help` | Slash help (welcome prompt) |

## What it does

1. **First launch** — forces resumable onboarding, validates structured values locally, optionally asks/reviews through OpenRouter with a local fallback, and creates `PROFILE.md`.
2. **Profile** — edits profile paths, one resume path, work-auth pack flags, and reusable portal Q&A.
3. **Apply** — opens a job URL in an ephemeral browser session, uses a saved credential when available, handles basic OTP/blocker flows, inventories fields, and resolves answers deterministically from the profile.
4. **Applications** — shows recorded values, sources, confidence, and artifact counts before preview approval and the experimental supervised-submit gate.

**OTP** (one-time code on a site) ≠ **OPT** (visa pack).

## Stack

- **UI:** Textual fullscreen workspace with status and navigation chrome
- **Profile truth:** Strict YAML front matter + readable sections in `PROFILE.md`
- **Application data:** SQLite (plaintext site credentials by explicit product policy, events, checkpoints, field actions)
- **Retrieval:** exact local mapping → lexical reusable-answer matching → ask user
- **Browser:** Playwright
- **LLM:** OpenRouter Settings health check plus privacy-bounded onboarding; Apply integration and LM Studio remain planned
- **Tooling:** `uv`, `pydantic-settings`

## Safety baseline

- Never invent application or work-auth facts
- Never bypass CAPTCHA or access controls
- SSNs/document numbers may live in `PROFILE.md`, but never enter RAG/cloud prompts
- Passwords are plaintext in SQLite, but password/OTP values are never copied into logs
- Screenshots redact password, OTP, SSN, passport, and license inputs
- Never retry ambiguous submits
- Unknown / sensitive questions go to you
- Submit requires a matching preview hash, explicit approval, and a one-use gate

The current preview covers recorded audit rows, not a fresh snapshot of the live page. Current-profile, live-DOM, blocker, and URL checks still need to be added at submit time.

## Project layout

```text
Terminal-Hire/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ docs/                 # FLOW, architecture, full product plan
├─ src/                   # application package
│  ├─ app.py              # TerminalHireApp
│  ├─ profile/             # PROFILE.md model, storage, retrieval
│  ├─ db/                  # SQLite credentials + application audit
│  ├─ browser/             # Playwright worker and evidence capture
│  ├─ apply/               # profile-backed application orchestration
│  ├─ llm/                 # OpenRouter/OpenAI-compatible client
│  └─ tui/                 # screens + theme
└─ tests/
```

Runtime files default outside this repository (for Windows: `%LOCALAPPDATA%\TUI-Hire`), which avoids accidental Git or OneDrive storage.

## Documents

| Doc | Role |
|---|---|
| [`docs/FLOW.md`](./docs/FLOW.md) | End-to-end TUI + system flows |
| [`docs/SYSTEM_ARCHITECTURE.md`](./docs/SYSTEM_ARCHITECTURE.md) | Build blueprint (modules, LLM switch, M0–M8) |
| [`docs/PROJECT.md`](./docs/PROJECT.md) | Full requirements (packs, data model, safety) |
| [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) | Code-backed status, gaps, priorities, and test coverage |
| [`docs/README.md`](./docs/README.md) | Docs index |
| [`.env.example`](./.env.example) | Config placeholders only — no real credentials |

For current behavior, **`IMPLEMENTATION_STATUS.md` wins**. For target stack and milestone order, `SYSTEM_ARCHITECTURE.md` wins.

## Config sketch

Copy `.env.example` → `.env`. Important knobs:

```text
LLM_PROVIDER=lmstudio          # lmstudio | openrouter | off
APPLICATION_DRY_RUN=true
APPLICATION_SUBMISSION_ENABLED=false
# DATA_DIR=C:\private\TUI-Hire  # optional override
```

To use Qwen through OpenRouter, keep the key only in your untracked `.env`:

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=  # add your key only in the untracked .env file
OPENROUTER_MODEL=qwen/qwen3.6-35b-a3b
OPENROUTER_PROVIDER=venice
OPENROUTER_ALLOW_FALLBACKS=false
ONBOARDING_AI_ENABLED=true
ONBOARDING_AI_MODEL=deepseek/deepseek-v4-flash
ONBOARDING_AI_MAX_REVIEW_ROUNDS=3
```

The OpenRouter adapter accepts explicit text, public image URLs, public video URLs,
or image/video data URLs. Those normal requests are pinned to Venice without provider
fallback. Use **Settings → Check connection** for a minimal authenticated request.

Private onboarding selects DeepSeek per call with OpenRouter automatic provider
routing. Structured identity, contact, location, authorization, and document values
are excluded; the model receives field-status metadata and professional text with
email, phone, and SSN-like patterns redacted.
Do not put other private identifiers inside professional-summary/history fields,
because those free-text patterns are not exhaustively scrubbed. Apply/form mapping
still does not call an LLM.

## Next steps

1. Revalidate profile hash, live page state, blockers, and URL immediately before Submit; enforce status transitions and a daily limit.
2. Expand synthetic browser coverage and add restart recovery before testing real ATS pages.
3. Strengthen onboarding free-text redaction and cloud-consent UX, then add the LM Studio adapter if still required.
4. Turn work-auth packs into real schemas/gates and add document validation, hashing, and LaTeX → PDF compilation.

## License

See repository for license terms once added.

# Terminal-Hire

**Hire from the terminal.** A local Python TUI for **US job applications**: build one verified `PROFILE.md`, reuse answers learned from job portals, fill with Playwright, capture an audit trail, and permit one supervised Submit click only after review.

Supervised submit is implemented but **off by default**.

## Status

| Area | State |
|---|---|
| Planning docs | Done (`docs/`) |
| Textual TUI shell | Done (welcome + FLOW screens) |
| Markdown profile + reusable Q&A | Implemented |
| First-run onboarding + profile editor | Implemented |
| SQLite credentials / application audit | Implemented |
| Playwright inventory/fill/checkpoints | Foundation implemented |
| Supervised submit | Implemented; opt-in and one-use |
| OpenRouter Qwen provider | Implemented for text, image, and video URL input |
| Agent / vector RAG | Planned; deterministic local retrieval works now |

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

1. **First launch** — forces resumable onboarding and creates `PROFILE.md`.
2. **Profile** — edits identity, SSN/document numbers, professional history, documents, work-auth packs, policies, and reusable portal Q&A.
3. **Apply** — opens a job URL, uses saved site credentials, requests OTP, inventories fields, and resolves each answer from the profile.
4. **Applications** — shows field values, sources, confidence, events, and screenshots before approval and supervised submit.

**OTP** (one-time code on a site) ≠ **OPT** (visa pack).

## Stack

- **UI:** Textual fullscreen workspace with status and navigation chrome
- **Profile truth:** Strict YAML front matter + readable sections in `PROFILE.md`
- **Application data:** SQLite (plaintext site credentials by explicit product policy, events, checkpoints, field actions)
- **Retrieval:** exact local mapping → lexical/RAG candidates → agent later → ask user
- **Browser:** Playwright
- **LLM:** OpenRouter through the OpenAI-compatible client; LM Studio adapter remains planned
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
| [`docs/README.md`](./docs/README.md) | Docs index |
| [`.env.example`](./.env.example) | Config placeholders only — no real credentials |

If docs disagree on stack or MVP order, **`SYSTEM_ARCHITECTURE.md` wins** until reconciled.

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
```

The OpenRouter adapter accepts explicit text, public image URLs, public video URLs,
or image/video data URLs. Requests are pinned to Venice without provider fallback.
It never attaches profile data or local files automatically.
Use **Settings → Check connection** to make a minimal authenticated model request.

## Next steps

1. Add schema-validated agent planning with minimal non-sensitive context.
2. Add the LM Studio adapter and a disposable local vector index.
3. Expand ATS-specific selectors, account creation, and browser recovery.
4. Add document hashing and LaTeX → PDF compilation.

## License

See repository for license terms once added.

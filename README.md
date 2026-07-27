# Terminal-Hire

**Hire from the terminal.** A local Python TUI for **US job applications**: build a verified profile (optional work-auth packs), compile a LaTeX resume to PDF, paste a career-page URL, and dry-run the application with Playwright — preview first, submit only when you allow it.

Inspired by [Grok Build](https://github.com/xai-org/grok-build)’s TUI patterns, reimplemented in **Python + Textual**. Not a `grok` CLI dependency.

Live submit stays **off** for the MVP.

## Status

| Area | State |
|---|---|
| Planning docs | Done (`docs/`) |
| Textual TUI shell | Done (welcome + FLOW screens) |
| Profile / agent / LLM | Not wired yet (M1–M2) |
| Resume compile | Stub (M3) |
| Playwright apply | Stub (M4–M5) |
| Live submit | Locked off |

## Quick start

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/MaharshPatelX/Terminal-Hire.git
cd Terminal-Hire
uv sync
cp .env.example .env   # optional; edit LLM settings later
uv run terminal-hire
```

Alternate launch:

```powershell
uv run python -m job_applyer
```

### Keyboard

| Key | Action |
|---|---|
| `1`–`6` | Onboard / Profile / Resume / Apply / Apps / Settings |
| `↑` `↓` `Enter` | Move welcome menu / open |
| `esc` | Home |
| `ctrl+q` | Quit |
| `/help` | Slash help (welcome prompt) |

## What it does (MVP direction)

1. **Onboard** — interview for verified core facts; enable only the work-auth packs you need (citizen / PR / OPT / STEM OPT / …).
2. **Resume** — store `.tex`, compile to PDF for uploads.
3. **Apply** — paste a US career URL → inventory fields → map from verified facts → dry-run fill → preview.
4. **Apps** — approve preview, enter site OTP, resume after CAPTCHA (never auto-solve).

**OTP** (one-time code on a site) ≠ **OPT** (visa pack).

## Stack

- **UI:** Textual (Grok Build–style welcome, status strip, screen chrome)
- **Data:** SQLite (+ optional Chroma RAG later)
- **Browser:** Playwright
- **LLM:** LM Studio and/or OpenRouter via one OpenAI-compatible client (`LLM_PROVIDER`)
- **Tooling:** `uv`, `pydantic-settings`

## Safety baseline

- Never invent application or work-auth facts
- Never bypass CAPTCHA or access controls
- Never leak secrets in logs
- Never retry ambiguous submits
- Unknown / sensitive questions go to you
- `APPLICATION_SUBMISSION_ENABLED=false` until dry-run quality is good and you flip policy

## Project layout

```text
Terminal-Hire/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ docs/                 # FLOW, architecture, full product plan
├─ src/job_applyer/      # package (product name: Terminal-Hire)
│  ├─ app.py             # TerminalHireApp
│  └─ tui/               # screens + theme
└─ data/                 # local DB / artifacts (gitignored)
```

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
DATABASE_URL=sqlite:///./data/terminal_hire.sqlite
```

## Next steps

1. Confirm default `LLM_PROVIDER` + model ids + LaTeX engine (M0)
2. M1 — SQLite profile store + real `llm-check`
3. M2 — agent onboard interview
4. M3 — LaTeX → PDF
5. M4–M5 — URL inventory → mapper → dry-run fill → approve

## License

See repository for license terms once added.

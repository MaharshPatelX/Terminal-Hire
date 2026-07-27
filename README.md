# Terminal-Hire

A planned **local Python TUI** for **US job applications**: interview you for a verified profile (optional work-auth **packs** — citizen / OPT / STEM OPT / etc. only if you need them), compile a LaTeX resume to PDF, then take a career-page URL and prepare (later optionally submit) applications with Playwright. Reasoning uses an **OpenAI-compatible client** pointed at **LM Studio** or **OpenRouter**. Agent structure is **inspired by Grok Build**, not dependent on the `grok` CLI.

Planning phase — UI shell started on `u/UI-dev`. Live submit stays off for the MVP.

## Planned MVP (active direction)

- **Textual TUI** primary UI: Onboard → Profile/Packs → Resume → Apply URL → Apps (preview/OTP).
- **US-only** apply; STEM OPT / H-1B are **optional packs**, not required for everyone.
- Own agent runtime → LM Studio **or** OpenRouter (`LLM_PROVIDER` switch).
- Playwright inventory + mapped fill; pause on site OTP/CAPTCHA/unknown; preview before submit.
- Optional Chroma RAG; SQLite source of truth.
- Safety: no invented facts, no CAPTCHA bypass, submit disabled until you enable it.

## Proposed stack

Python, **Textual** TUI, SQLite, Playwright, Chroma (optional), LM Studio and/or OpenRouter (OpenAI-compatible `/v1`), LaTeX → PDF.

## Safety baseline

Never invent application or work-auth facts, bypass CAPTCHA or access controls, leak secrets in logs, or retry ambiguous submits. Unknown/sensitive questions go to you. Live submission stays off until dry-run quality is good and you flip an explicit policy.

## Documents

All planning docs live under [`docs/`](./docs/):

- [`docs/FLOW.md`](./docs/FLOW.md) — **end-to-end TUI + system flows** (start here to understand the product path).
- [`docs/SYSTEM_ARCHITECTURE.md`](./docs/SYSTEM_ARCHITECTURE.md) — **active build blueprint** (modules, TUI, LLM switch, milestones).
- [`docs/PROJECT.md`](./docs/PROJECT.md) — **full product plan** (US scope, profile packs, data model, safety, MVP vs future).
- [`docs/README.md`](./docs/README.md) — docs index.
- [`.env.example`](./.env.example) — placeholder configuration only; no real credentials.

## Run the TUI

```powershell
uv sync
uv run terminal-hire
# or
uv run python -m job_applyer
```

Keys: `1–6` screens · `esc` home · `ctrl+q` quit · `/help` in the welcome prompt.

## Next step

Confirm default `LLM_PROVIDER` and model ids, then implement M1→M5 (TUI shell → onboard → resume → URL inventory → dry-run).

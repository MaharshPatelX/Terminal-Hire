# Terminal-Hire — Documentation

Active product and implementation documentation for **TUI-Hire / Terminal-Hire**, a local Python TUI for audited US job applications.

## Naming

| Use | Value |
|---|---|
| Product name | **Terminal-Hire** |
| Python package | `src` |
| Launch | `uv run terminal-hire` or `uv run python -m src` |
| Windows data home | `%LOCALAPPDATA%\TUI-Hire` |
| Profile truth | `PROFILE.md` |
| Application store | `terminal_hire.sqlite` |

## Start here

| Doc | Role |
|---|---|
| [`FLOW.md`](./FLOW.md) | Current onboarding, retrieval, browser, review, and submit flow |
| [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md) | **Active build blueprint** — modules, TUI, LLM switch, milestones M0–M8 |
| [`PROJECT.md`](./PROJECT.md) | Full product/requirements plan — US scope, packs, data model, safety, MVP vs future |

If docs disagree on **stack or MVP order**, `SYSTEM_ARCHITECTURE.md` wins until both are updated together.

Root summary: [`../README.md`](../README.md)  
Config template: [`../.env.example`](../.env.example)

## Future docs (placeholders)

| Folder | Purpose |
|---|---|
| [`adr/`](./adr/) | Architecture Decision Records for material deviations |
| [`runbooks/`](./runbooks/) | Operational how-tos (LLM check, dry-run recovery, etc.) |
| [`threat-model/`](./threat-model/) | Security/privacy notes for sensitive local data and supervised submit |

## Status

- **Phase:** implementation (aligned 2026-07-27)
- **Implemented foundation:** PROFILE.md, onboarding/profile UI, SQLite audit, browser worker, review, one-use submit gate
- **Next:** synthetic browser fixtures, LLM adapter, non-sensitive local RAG, ATS hardening, document build

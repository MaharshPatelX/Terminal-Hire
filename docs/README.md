# Terminal-Hire — Documentation

Product, architecture, flow, and code-backed status documentation for **TUI-Hire / Terminal-Hire**, a local Python TUI prototype for supervised US job applications.

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
| [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) | **Current code truth** — implemented, standalone, planned, risks, configuration, and test coverage |
| [`FLOW.md`](./FLOW.md) | Current onboarding, retrieval, browser, review, and submit flow |
| [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md) | **Active build blueprint** — modules, TUI, LLM switch, milestones M0–M8 |
| [`PROJECT.md`](./PROJECT.md) | Full product/requirements plan — US scope, packs, data model, safety, MVP vs future |

If docs disagree about **current behavior**, `IMPLEMENTATION_STATUS.md` wins. If they disagree on **target stack or MVP order**, `SYSTEM_ARCHITECTURE.md` wins until reconciled.

Root summary: [`../README.md`](../README.md)  
Config template: [`../.env.example`](../.env.example)

## Future docs (placeholders)

| Folder | Purpose |
|---|---|
| [`adr/`](./adr/) | Architecture Decision Records for material deviations |
| [`runbooks/`](./runbooks/) | Operational how-tos (LLM check, dry-run recovery, etc.) |
| [`threat-model/`](./threat-model/) | Security/privacy notes for sensitive local data and supervised submit |

## Status

- **Phase:** prototype implementation (audited 2026-08-02 at `f4176c7`)
- **Passing baseline:** 43 tests
- **Implemented foundation:** PROFILE.md, locally validated and OpenRouter-assisted private onboarding, profile UI, SQLite audit, generic browser worker, audit preview, one-use submit claim
- **Integrated LLM scope:** OpenRouter onboarding and Settings health check only; Apply/form mapping remains deterministic
- **Not integrated:** LLM-driven onboarding/mapping, LM Studio, vector RAG
- **Highest priority:** submit-time freshness/blocker/URL checks, lifecycle enforcement, synthetic browser coverage, and restart recovery

Private onboarding was merged by PR #11 before this documentation branch was finalized. The audit branch is rebased onto that updated `main`.

# Terminal-Hire — Documentation

Planning baseline for **Terminal-Hire**: a local Python TUI that helps with **US job applications**. No application code yet.

## Naming

| Use | Value |
|---|---|
| Product name | **Terminal-Hire** |
| Python package | `terminal_hire` |
| Launch (planned) | `python -m terminal_hire` |
| Data dir / DB (planned) | `./data/terminal_hire.sqlite` |

## Start here

| Doc | Role |
|---|---|
| [`FLOW.md`](./FLOW.md) | End-to-end TUI + system flows (product path) |
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
| [`threat-model/`](./threat-model/) | Security / privacy threat notes before live submit |

## Status

- **Phase:** planning (aligned 2026-07-26)
- **Implementation:** not started
- **Next:** resolve open decisions (default `LLM_PROVIDER`, model ids, LaTeX engine), then M1

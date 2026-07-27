# Terminal-Hire — End-to-End Flow (TUI)

Status: planning  
Last updated: 2026-07-26  
UI: **Python TUI** (Textual + Rich) as the primary interface  
See also: [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md), [`PROJECT.md`](./PROJECT.md), [`README.md`](./README.md)

This file is the **user + system flow map**. Use it when wiring screens, state machines, and agent steps.

---

## 1. Big picture

```text
                    ┌─────────────────────────────┐
                    │   Terminal-Hire TUI (Textual) │
                    │   single local fullscreen   │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         v                         v                         v
   Profile / Packs           Apply workspace            Settings
   Onboard chat              URL → dry-run → OTP        LLM switch
   Resume LaTeX→PDF          Preview / Approve          Paths, safety
         │                         │
         v                         v
   SQLite + files            Playwright + Agent
   (optional Chroma)         LM Studio | OpenRouter
```

**Scope:** US job applications. Work-auth (citizen / OPT / STEM OPT / …) = optional **packs**.  
**Site OTP** (one-time code) ≠ **OPT** (visa pack).

---

## 2. TUI navigation map

Launch: `terminal-hire` or `python -m terminal_hire` → fullscreen TUI.

```text
┌─ Home ─────────────────────────────────────────────────────┐
│  [Onboard] [Profile] [Resume] [Apply] [Apps] [Settings]    │
│                                                            │
│  Status strip: LLM=lmstudio · Dry-run ON · Packs: …        │
└────────────────────────────────────────────────────────────┘
```

| Screen | Purpose |
|---|---|
| **Home** | Summary: profile ready?, resume PDF?, open blockers, recent apps |
| **Onboard** | Chat-style interview with local agent; verify facts; pick packs |
| **Profile** | Browse/edit/verify facts; enable/disable packs |
| **Resume** | Add `.tex`, build PDF, see path/hash |
| **Apply** | Paste US career URL → run dry-run pipeline → live progress |
| **Apps** | List applications by status; open detail; Approve / OTP / Cancel |
| **Settings** | `LLM_PROVIDER`, model ids, paths, dry-run/submit flags (submit locked) |
| **Ask** (optional pane) | Freeform coach against profile (read-only tools) |

Optional later: headless/script commands that call the same services the TUI uses. TUI is the product UI.

---

## 3. Master lifecycle (happy path)

```text
[1] First launch
      └─> Settings: pick LLM (LM Studio or OpenRouter) → llm-check OK
            └─> Onboard
                  ├─ US market confirmed
                  ├─ Core facts collected + verified
                  ├─ Packs chosen (or none)
                  ├─ Pack facts collected + verified
                  └─> Resume: add .tex → build PDF
                        └─> Apply: paste URL
                              ├─ Playwright opens page
                              ├─ Inventory fields
                              ├─ Agent maps fields (core+packs only)
                              ├─ Dry-run fill + upload PDF
                              ├─ Preview shown in TUI
                              └─> User Approve
                                    ├─ (if site OTP) enter code in TUI → resume
                                    ├─ (if CAPTCHA) pause → user solves in browser → resume
                                    └─> STOP before submit (MVP)
                                          └─> Apps list shows waiting / done dry-run
```

---

## 4. Flow A — First-time setup (Onboard + Resume)

```text
Home ──> Onboard screen
            │
            │  Agent role: onboarder (LM Studio | OpenRouter)
            ▼
        Q: "Applying to US jobs?" → yes (this phase)
            │
            ▼
        CORE interview loop
            ask → user answers in TUI input
                → save draft fact
                → user taps Verify (or batch verify)
                → optional embed to Chroma
            │
            ▼
        Pack picker (multi-select)
            [ ] US_CITIZEN  [ ] US_PR  [ ] OTHER_US_AUTH
            [ ] F1_OPT      [ ] STEM_OPT   (H1B later)
            │
            │  only enabled packs get questions
            ▼
        PACK interview loop (skip if none)
            │
            ▼
        Onboard complete banner → go to Resume
            │
            ▼
        Resume screen
            add path to .tex → Build → show PDF ready
            │
            ▼
        Home shows: Profile ✓  Resume ✓  Ready to apply
```

**Rules**

- Disabled packs: no questions, no facts, no mapper context.
- Model cannot mark facts verified — only the user can.
- STEM OPT legal caution text only appears if `STEM_OPT` is enabled.

---

## 5. Flow B — Apply by URL (dry-run)

```text
Apply screen
   user pastes: https://company.com/jobs/123
   taps [Start dry-run]
        │
        ▼
   Create/link Job (market=US) + Application (status=ready_to_apply)
        │
        ▼
   status=applying
   Playwright opens URL (headful recommended while developing)
        │
        ├─ login wall / unexpected → blocker → Apps detail (pause)
        ├─ CAPTCHA detected → status=blocked_by_captcha → user handles in browser → [Resume]
        │
        ▼
   Inventory form fields → form_snapshots
   Save job text → optional RAG embed
        │
        ▼
   Agent role: form_mapper
   Input: inventory JSON + core facts + enabled-pack facts + RAG hits
   Output: fill-plan JSON (validated)
        │
        ├─ invalid JSON → fail safely, ask retry / manual
        ├─ ask_user actions → TUI prompts for answers → save as facts or one-off
        │
        ▼
   Playwright executes plan (fill / upload PDF / skip)
   Never clicks Submit in MVP (network guard)
        │
        ▼
   Build preview report + preview_hash
   status=waiting_for_user_review
        │
        ▼
   Apps → Application detail
        show mapped fields (secrets masked)
        [Approve preview] [Cancel] [Edit answer…]
```

### After Approve

```text
Approve preview (hash must match)
        │
        ├─ OTP field/step detected → status=waiting_for_otp
        │       TUI: enter one-time code → inject → continue applying
        │
        ├─ more unknown fields → back to review
        │
        └─ MVP: mark dry-run complete / ready for future submit
               Submit button hidden or disabled while
               APPLICATION_SUBMISSION_ENABLED=false
```

---

## 6. Flow C — Blockers (OTP / CAPTCHA / unknown)

```text
                    ┌──────────────────┐
                    │  applying        │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┐
           v                 v                 v
   waiting_for_otp   blocked_by_captcha   waiting_for_user_review
           │                 │                 │
           │ TUI OTP input   │ user solves     │ Approve / answer
           │                 │ in browser      │
           └────────┬────────┴────────┬────────┘
                    v                 v
                 applying  <── [Resume]
                    │
                    ├─ success path (dry-run done)
                    └─ failed → Apps shows reason → retry later
```

| Blocker | TUI action | System action |
|---|---|---|
| Site OTP | Enter code (masked, not logged) | Short-TTL use → delete |
| CAPTCHA | Instruction + Resume | Never solve/bypass |
| Unknown / sensitive Q | Answer or Decline per policy | Save verified or skip |
| Consent / terms | User must accept in browser | Pause until confirmed |

---

## 7. Flow D — Settings / LLM switch

```text
Settings
  LLM_PROVIDER: ( ) lmstudio  ( ) openrouter  ( ) off
  LM Studio URL / model
  OpenRouter key / model
  [Check connection]
  Dry-run: ON (forced MVP)
  Submit: OFF (locked MVP)
  Packs shortcut → Profile
```

Same OpenAI-compatible client; only base URL + key + model change.  
Both providers can be configured; only one is active.

---

## 8. Flow E — Future supervised submit (not MVP)

```text
Approved dry-run + APPLICATION_SUBMISSION_ENABLED=true
  → re-check gates (PROJECT.md §8.3)
  → single submit click
  → confirmation artifact
  → status=submitted
  → later: interview / rejected / offer
```

CAPTCHA still never auto-solved. Ambiguous click → human reconcile, no blind retry.

---

## 9. Flow F — Future US discovery (not MVP)

```text
Collectors (Greenhouse/Lever/Ashby) → jobs DB
  → optional match/score (pack-aware)
  → user picks job in TUI → same Apply dry-run flow from §5
```

MVP entry is still **paste URL** on Apply screen.

---

## 10. Application status (as shown in TUI Apps)

```text
ready_to_apply
    → applying
        → waiting_for_user_review → (Approve) → applying
        → waiting_for_otp → (code) → applying
        → blocked_by_captcha → (Resume) → applying
        → failed → (Retry) → ready_to_apply
        → submitted (future)
            → interview | rejected | offer
```

---

## 11. Data movement (one apply)

```text
TUI Apply
  → orchestrator
      → Playwright: DOM inventory
      → SQLite: jobs, form_snapshots, applications
      → Agent + LLM: fill plan
      → SQLite: field_mappings
      → Playwright: fill + PDF upload
      → artifacts/: redacted screenshot/report
      → TUI Apps: preview
      → user Approve / OTP
      → audit_events always
```

**Never in logs:** OTP codes, full SSN/immigration docs, raw restricted answers.

---

## 12. TUI screen → backend services

| TUI screen | Calls |
|---|---|
| Onboard | `agent.onboarder` → `profile.facts` → optional `rag.embed` |
| Profile / Packs | `profile.packs` / `profile.facts` |
| Resume | `resume.latex` / `documents` |
| Apply | `apply.orchestrator` → `browser` → `agent.form_mapper` |
| Apps | `apply` status / approve / otp / cancel |
| Settings | `config` / `llm.check` / provider switch |
| Ask | `agent.coach` (read-only) |

Shared library under `src/terminal_hire/`; TUI is a thin reactive layer (`tui/`), not business logic.

---

## 13. Sequence — dry-run apply (detail)

```text
User          TUI           Orchestrator      Browser         Agent/LLM         DB
 │             │                 │               │               │              │
 │ paste URL   │                 │               │               │              │
 │────────────>│ start           │               │               │              │
 │             │────────────────>│ create app    │               │              │
 │             │                 │─────────────────────────────────────────────>│
 │             │                 │ open          │               │              │
 │             │                 │──────────────>│               │              │
 │             │                 │ inventory     │               │              │
 │             │                 │<──────────────│               │              │
 │             │                 │ save snapshot │               │              │
 │             │                 │─────────────────────────────────────────────>│
 │             │                 │ map(fields,facts)             │              │
 │             │                 │──────────────────────────────>│              │
 │             │                 │ fill plan JSON│               │              │
 │             │                 │<──────────────────────────────│              │
 │             │                 │ fill/upload   │               │              │
 │             │                 │──────────────>│               │              │
 │             │ preview         │               │               │              │
 │             │<────────────────│               │               │              │
 │ Approve     │                 │               │               │              │
 │────────────>│ approve         │               │               │              │
 │             │────────────────>│               │               │              │
 │ (OTP?)      │                 │               │               │              │
 │────────────>│ otp             │ inject        │               │              │
 │             │────────────────>│──────────────>│               │              │
 │             │ done (no submit)│               │               │              │
 │             │<────────────────│               │               │              │
```

---

## 14. Error / edge flows (short)

| Case | Flow |
|---|---|
| LLM provider down | Settings → Check fails; Apply/Onboard blocked with clear message; switch provider or fix LM Studio |
| Bad URL / non-US hint | Warn in Apply; user can continue or cancel |
| LaTeX build fail | Resume screen shows compiler error; no PDF upload until fixed |
| Mapper low confidence | Preview highlights fields; force user review |
| Browser crash | Checkpoint → Apps → Resume from last step |
| Pack disabled mid-way | Mapper stops using those facts; may create new ask_user blockers |

---

## 15. MVP flow checklist (acceptance)

- [ ] TUI launches; Settings can switch LM Studio ↔ OpenRouter and check health  
- [ ] Onboard completes core + optional packs; verify works  
- [ ] Resume builds PDF  
- [ ] Apply URL → inventory → mapped dry-run → preview in Apps  
- [ ] OTP / CAPTCHA / unknown pause and resume from TUI  
- [ ] Submit impossible while flag off  
- [ ] Disabled packs never appear in mapper context  

---

## 16. What is *not* in the MVP flow

- Live submit  
- Auto email OTP reading  
- CAPTCHA solving  
- ATS board crawling / match inbox (future entry into same Apply flow)  
- Multi-country markets  
- STEM/H-1B logic unless those packs are enabled  

# Terminal-Hire — Implementation Status and Gap Audit

Status: code-backed snapshot, not a product promise
Audited: 2026-08-02
Baseline: `origin/main` at merge commit `f4176c7`, including private-onboarding commit `7254f1c`
Verification: `uv run --frozen --extra dev pytest -p no:cacheprovider` — 43 passed

This is the source of truth for what the committed repository currently implements. `SYSTEM_ARCHITECTURE.md` and `PROJECT.md` describe the target design; this file records the distance between that design and the code.

## Status vocabulary

| Label | Meaning |
|---|---|
| Implemented | Connected to the application and covered by relevant automated tests |
| Foundation | Working narrow path, but missing breadth, recovery, or production hardening |
| Standalone | Code exists and is tested, but is not used by the main apply workflow |
| Planned | Described in docs or configuration comments, but no implementation exists |

## Current implementation

| Area | Status | What exists now |
|---|---|---|
| Textual application shell | Implemented | Forced first-run onboarding, ready-state home, Profile, Apply, Applications, Settings, keyboard and slash navigation |
| `PROFILE.md` | Implemented | Strict Pydantic model, YAML front matter, readable rendering, atomic replacement, one backup, schema-version check, content hash |
| Private-AI onboarding | Implemented foundation | Staged local questions, semantic validation, file existence check, local review, safe projection, optional redacted OpenRouter question/review, bounded review rounds, local fallback |
| Profile editing | Foundation | Generic field-path editor, list editing, reusable global/company Q&A, one resume path, pack checkboxes, verification |
| Retrieval | Implemented foundation | Structured aliases, common answers, lexical portal-Q&A matching, provenance/confidence, ask-user fallback, non-sensitive `safe_context` projection |
| SQLite audit | Implemented foundation | Credentials, runtime setting, applications, events, field actions, checkpoints, artifacts, preview-bound approvals |
| Browser automation | Foundation | One ephemeral Chromium session; generic login/continue, OTP entry, field inventory/fill/upload, screenshots, basic blockers |
| Review and submit | Foundation | Audit-record preview hash, explicit approval, atomic one-use claim, exactly one visible submit control, uncertain-result stop |
| OpenRouter | Integrated for onboarding only | Text/image/video-URL client, Settings health check, JSON chat, per-call onboarding model, and automatic provider routing; not used by Apply/form mapping |
| LM Studio | Planned | Provider name appears in Settings and config examples; no client or connection check |
| Agent runtime / vector RAG | Planned | No `agent/` runtime, tools, roles, embeddings, or vector index; lexical `safe_context` is not consumed |
| Resume build | Planned | A saved path can be uploaded; no LaTeX compilation, validation, or document hashing |
| ATS support | Planned | Generic DOM selectors only; no ATS detection or adapters |
| Restart recovery | Planned | Checkpoints are written but never loaded; browser contexts are ephemeral |
| Retention, limits, observability | Planned | No cleanup jobs, daily application limit, concurrency controller, metrics, structured logging, or model-run audit |

## Important gaps

### P0 — required before treating Submit as production-safe

1. **Submit does not revalidate the current profile hash.** A test proves that calling `update_application_profile` invalidates approval, but profile edits do not automatically call that method for open applications. The Applications screen can therefore hold an approval created from an older profile snapshot.
2. **The preview hashes audit rows, not live browser state.** Manual page edits, dynamic validation, newly appeared fields, or DOM changes after preview are not compared before Submit.
3. **The documented URL/domain gate is absent.** Submit checks the approval and button count, but it does not assert that the current page still belongs to the audited job URL/domain.
4. **Blocker safety depends on best-effort detection.** CAPTCHA, consent, and OTP checks are selector/text heuristics and are not guaranteed to run before every review/submit path. There is no final blocker scan in `submit_once`.
5. **Statuses are free-form strings.** `LocalStore.set_status` accepts any value and does not enforce the lifecycle described in the docs or record a dedicated transition history.
6. **No submission rate limit exists.** `APPLICATION_DAILY_LIMIT` was documented, but the committed `Settings` model and submit gate do not load or enforce it.

Until these are fixed and tested, supervised Submit should remain disabled except for controlled development fixtures.

### P1 — needed for a reliable MVP

1. Add synthetic tests for login/sign-up, consent, OTP, CAPTCHA, required-field validation, select/checkbox/radio edge cases, multi-step navigation, redirects, and ambiguous confirmation.
2. Add browser restart recovery or clearly mark attempts as non-resumable. Current checkpoints are audit records only.
3. Harden the new onboarding privacy boundary. Structured local values are excluded, but free-form professional text is pattern-redacted only for email, phone, and SSN-like values; names, addresses, or other identifiers typed into professional fields could still be sent.
4. Make onboarding cloud use explicit in UX. When `LLM_PROVIDER=openrouter` and `ONBOARDING_AI_ENABLED=true`, question selection/review calls OpenRouter automatically and uses automatic provider routing rather than the configured Venice-only route.
5. Turn pack checkboxes into real schemas and mapping gates. Today they are stored/displayed flags; they do not control pack-specific questions or retrieval.
6. Reconcile field actions. Re-filling a field appends another row, and the preview contains history rather than a canonical current field set.
7. Add URL validation and explicit policy for redirects/account domains.
8. Decide whether `APPLICATION_DRY_RUN` is a real gate or remove it. It is loaded but does not control browser or submit behavior.

### P2 — planned product capabilities

- Integrate a schema-validated agent mapper using only minimal non-sensitive context.
- Implement the LM Studio adapter and provider factory.
- Add disposable local semantic retrieval if lexical retrieval proves insufficient.
- Add LaTeX-to-PDF build, file validation, and SHA-256 document registration.
- Add ATS-specific adapters, durable sessions, retention cleanup, audit export, metrics, and model-run metadata.
- Add email OTP only if a separate security review approves it; never automate CAPTCHA bypass.

## Configuration truth

The `Settings` model currently loads:

- `LLM_PROVIDER`
- OpenRouter key/base URL/model/provider/fallback/header/timeout values
- `APPLICATION_DRY_RUN` and `APPLICATION_SUBMISSION_ENABLED`
- `PLAYWRIGHT_HEADLESS`
- `APP_TIMEZONE`, `DATA_DIR`, filenames, artifact directory, and optional SQLite URL
- `ONBOARDING_AI_ENABLED`, `ONBOARDING_AI_MODEL`, and `ONBOARDING_AI_MAX_REVIEW_ROUNDS`

The following names appeared in the old config sketch but are not loaded or enforced: `APPLICATION_DAILY_LIMIT`, `LOG_LEVEL`, every `LMSTUDIO_*` value, `OPENROUTER_ENABLED`, shared agent/LLM tuning values, `BROWSER_MAX_CONCURRENCY`, `EMAIL_OTP_ENABLED`, and all retention values. They remain roadmap items and are no longer presented as active configuration in `.env.example`.

The Settings provider selector changes only the current in-memory setting. Only the supervised-submit toggle is persisted in SQLite. OpenRouter's connection check is wired; LM Studio's is not.

## Test coverage

The 43 tests cover:

- profile round-trip, backup recovery, schema versioning, readiness, and sensitive-context exclusion;
- lexical reusable-answer matching and structured alias behavior;
- credential storage policy, event/field redaction, preview invalidation, blocker statuses, cancellation, and one-use approval;
- a synthetic generic form with text, SSN, file, radio, screenshots, and one-click submit;
- rejection of multiple submit controls;
- OpenRouter request shape/configuration/error handling;
- structured onboarding validation, US postal validation, pending invalid values, professional-text redaction, work/education completeness, AI path allowlisting, model override/routing, input focus, and invalid-ZIP persistence;
- first-launch and ready-state TUI routing.

Neither suite proves real ATS compatibility, login/OTP/CAPTCHA recovery, multi-step forms, restart recovery, retention, rate limits, live-page preview integrity, real provider connectivity, or production submit safety.

## Audit provenance

The private-onboarding work was first inspected and tested read-only while uncommitted. It was then committed as `7254f1c`, merged by PR #11 into `origin/main` as `f4176c7`, and used as the final base for this documentation branch. The user's primary checkout was never switched by this audit.

# Terminal-Hire — Current End-to-End Flow

Status: committed implementation flow; planned steps are labeled
Last updated: 2026-08-02 (audited at `f4176c7`)
UI: Python Textual TUI

See also: [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md), [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md), [`PROJECT.md`](./PROJECT.md), and [`README.md`](./README.md).

## 1. Big picture

```text
First launch
  -> Onboard
  -> atomic PROFILE.md drafts
  -> user review + VERIFY
  -> ready workspace

Ready workspace
  -> Profile
  -> Apply
  -> Applications
  -> Settings

Apply
  -> URL + site credential
  -> best-effort Playwright login/continue
  -> consent/CAPTCHA/OTP pause
  -> field inventory
  -> deterministic PROFILE.md retrieval
  -> field-by-field fill + evidence
  -> final review
  -> exact preview approval
  -> optional one-use Submit click
```

## 2. Local data

Runtime files default outside the repository and OneDrive.

```text
%LOCALAPPDATA%\TUI-Hire\
  PROFILE.md
  PROFILE.md.bak
  terminal_hire.sqlite
  artifacts\
    <application-id>\
      0001-opened.png
      0002-login-filled.png
      ...
```

### `PROFILE.md`

The only source of truth for user details:

- identity, contact, address, SSN, and government-document numbers
- professional summary, education, work history, projects, and skills
- work authorization and enabled packs
- resume/document paths
- common application answers and answer policies
- every reusable portal question/answer, normalized intent, scope, verification, and provenance
- user insights learned during applications

Strict YAML front matter is machine-authoritative. The Markdown body is a readable rendering.

### SQLite

SQLite does not own profile truth. It stores:

- site accounts and plaintext passwords by explicit product policy
- applications and their exact `PROFILE.md` content hash
- ordered browser/application events
- field values or redactions, value hashes, sources, and confidence
- browser checkpoints
- screenshot/artifact paths
- preview-bound one-use submit approvals

Passwords, OTPs, SSNs, and document values are never copied into event values.

## 3. Navigation

### First launch or broken profile

```text
missing / invalid / incomplete / unverified PROFILE.md
  -> Onboard
```

Settings remains reachable from onboarding with `/settings`. A malformed file is not overwritten; `/recover` restores the last valid backup.

### Ready launch

```text
1 Profile
2 Apply
3 Applications
4 Settings
```

Onboarding disappears from normal navigation. Profile becomes the permanent editing surface.

## 4. Onboarding

```text
Ask one question
  -> user answer
  -> update typed profile model
  -> validate
  -> atomic PROFILE.md save
  -> retain previous valid file as backup
  -> ask next question
```

Onboarding collects:

1. legal name, email, and phone
2. structured address
3. professional summary, education, work history, projects, and skills
4. work authorization and sponsorship
5. optional primary resume/document path
6. final local review and user verification

The user types `VERIFY` to mark the profile complete. Onboarding does not collect SSN, passport, license, or alien-registration values; those remain optional Profile-editor fields.

### Private-AI onboarding

The committed staged `OnboardingFlow`:

- local validation for names, email, phone, location, country-aware postal codes, yes/no answers, professional-summary length, lists, and resume-file existence;
- a local completeness review that requires work history or education;
- optional OpenRouter question phrasing, correction phrasing, and up to three professional-profile review rounds;
- allowlisted question paths and AI issues, repeated-review detection, and local fallback when AI is off or unavailable;
- no SSN/passport/license questions during onboarding; those profile fields remain editable later.

With `LLM_PROVIDER=openrouter` and `ONBOARDING_AI_ENABLED=true`, the AI receives field presence/missing statuses plus professional summary, education, work history, projects, and skills. Structured identity, contact, location, authorization, and document **values** are excluded. Email, phone, and SSN-like patterns are removed from professional text, but free text is not an exhaustive PII scrubber; names, addresses, or other identifiers typed into professional fields could leave the machine. The onboarding model uses OpenRouter automatic provider routing rather than the normal Venice-only route.

## 5. Profile editing

Profile supports:

- edit a strict field path such as `identity.full_name`, `contact.email`, or `sensitive_identity.ssn`
- edit list fields with `|` separators
- store work-authorization pack flags
- set the primary resume/document path
- add reusable portal Q&A with global or company scope
- preview the complete generated `PROFILE.md`
- verify the current profile

All changes use the same validated atomic writer as onboarding.

Pack flags are not yet pack schemas: they do not add pack-specific questions or gate the generic work-authorization lookup.

## 6. Start an application

```text
Apply screen
  -> paste job/application URL
  -> optional company name
  -> load verified PROFILE.md snapshot
  -> create SQLite application
  -> store profile content hash
```

If the profile is not complete and verified, Apply is blocked and the user returns to onboarding.

## 7. Credentials, login, account creation, and OTP

1. User enters site email/username/password.
2. Password is stored as plaintext in OS-local SQLite.
3. Audit events record only that a credential was filled, never the value.
4. Playwright detects email, username, password, and password-confirmation inputs.
5. One matching login, sign-up, registration, create-account, continue, or next button can be clicked best-effort; this is not a complete account-creation workflow.
6. Unchecked terms/consent pause for manual review.
7. CAPTCHA always pauses for the user.
8. OTP is requested in the TUI, filled once, cleared from memory, and never persisted.

Browser sessions are ephemeral. Checkpoints are audit records and are not loaded to resume after process restart.

## 8. Field retrieval

For every form field, the committed resolver uses:

```text
1. Exact structured PROFILE.md alias
   -> email, phone, first/last name, address, work authorization, SSN, etc.

2. Similar `common_answers` or verified reusable portal Q&A
   -> global answer or company-scoped answer

3. Ask the user
   -> use once
   -> or save verified answer to PROFILE.md and reuse later
```

`ProfileRetriever.safe_context` can produce ranked, non-sensitive lexical chunks, but no Apply workflow consumes them. Agentic/vector RAG and form-mapping LLM reasoning are planned. The OpenRouter client is used by the Settings connection check and private onboarding only.

SSN and government-document values stop at step 1. The existing context projection excludes them, and no current Apply path sends profile content to an LLM.

Low-confidence retrieval never fills automatically.

## 9. Fill and evidence

For each filled field:

1. Fill/select/check with Playwright.
2. Record field name and portal question.
3. Record profile source and confidence.
4. Store ordinary values; redact sensitive values and store only their hash.
5. Save an ordered event.
6. Capture a screenshot with password, OTP, SSN, passport, and license inputs blurred.
7. Save checkpoints for page-open and inventory stages; per-field recovery checkpoints are not implemented.

Unknown fields change the application to `waiting_for_user_answer`.

## 10. Review

After fields are ready:

```text
field actions
  -> stable JSON
  -> SHA-256 preview hash
  -> status waiting_for_user_review
```

Applications shows:

- URL, company, status, and profile hash
- every field value or sensitive placeholder
- source, confidence, and result
- event and artifact counts
- recent screenshot paths

Approval is bound to the exact preview hash. Any profile or field change invalidates the old preview and approval.

The hash covers recorded `field_actions`, including history. It is not a snapshot of the live DOM. A profile change invalidates approval only after the application service adopts the new profile hash; editing `PROFILE.md` elsewhere does not currently update every open application automatically.

## 11. Supervised submit

Submission is disabled by default in Settings.

When enabled, the committed gate checks:

1. application status is `approved`
2. current stored preview hash matches the explicit approval
3. active audited browser session exists
4. approval was not previously consumed
5. exactly one visible, enabled Submit control is detected

The approval is atomically consumed before Playwright clicks Submit.

Production-critical final checks are still missing: refresh and compare the current profile hash, rescan blockers and required fields, compare the live DOM with the preview, and assert the current URL/domain. Keep Submit disabled outside controlled development fixtures until these are implemented and tested.

```text
known confirmation phrase detected
  -> submitted

missing or ambiguous confirmation
  -> submission_uncertain
  -> user reconciles manually
  -> no automatic retry
```

## 12. Application statuses

```text
ready_to_apply
  -> applying
      -> waiting_for_credential -> applying
      -> waiting_for_user_answer -> applying
      -> waiting_for_otp -> applying
      -> blocked_by_captcha -> applying
      -> waiting_for_consent -> applying
      -> waiting_for_user_review
          -> approved
              -> submitting
                  -> submitted
                  -> submission_uncertain
      -> cancelled
```

## 13. Screen to service map

| Screen | Services |
|---|---|
| Onboard | `profile.ProfileService` + `MarkdownProfileRepository` |
| Profile | profile edit/Q&A/document/pack services |
| Apply | `ApplicationService`, `ProfileRetriever`, `LocalStore`, `BrowserSession` |
| Applications | field/evidence review, preview approval, supervised submit |
| Settings | provider, local path display, persisted submit policy |

## 14. Implemented now

- strict Markdown profile model, rendering, validation, atomic save, backup, and recovery
- deterministic field aliases and reusable-Q&A retrieval
- sensitive values excluded from search context
- SQLite credentials, application events, field actions, checkpoints, artifacts, and one-use approvals
- first-run routing and four-item ready navigation
- onboarding and profile editing
- private onboarding with local validation and redacted OpenRouter review
- Playwright login/account/OTP/inventory/fill/evidence foundation
- final review and supervised-submit gate
- standalone OpenRouter multimodal client and Settings connection check
- 28 automated profile, storage, browser, LLM-client, gate, and TUI routing tests

## 15. Next hardening

- submit-time profile/live-DOM/blocker/URL validation, legal status transitions, and daily limits
- synthetic browser fixtures for login, sign-up, OTP, CAPTCHA, consent, multi-step forms, redirects, validation, and confirmation
- persistent browser recovery after process restart
- strengthen onboarding free-text redaction and make cloud routing/consent explicit
- schema-validated application mapper plus LM Studio adapter if retained
- disposable local vector index for non-sensitive profile chunks
- ATS-specific selectors and form adapters
- LaTeX/PDF build and document hashing

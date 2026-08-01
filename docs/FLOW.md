# Terminal-Hire — Current End-to-End Flow

Status: active product and implementation flow
Last updated: 2026-07-27
UI: Python Textual TUI

See also: [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md), [`PROJECT.md`](./PROJECT.md), and [`README.md`](./README.md).

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
  -> Playwright login/account creation
  -> consent/CAPTCHA/OTP pause
  -> field inventory
  -> PROFILE.md retrieval
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
3. professional summary
4. education, work history, projects, and skills
5. work authorization and sponsorship
6. optional SSN and government-document numbers
7. optional primary resume/document path
8. final user verification

Sensitive input is masked and shown only as “saved sensitive value.” The user types `VERIFY` to mark the profile complete.

## 5. Profile editing

Profile supports:

- edit a strict field path such as `identity.full_name`, `contact.email`, or `sensitive_identity.ssn`
- edit list fields with `|` separators
- enable or disable work-authorization packs
- set the primary resume/document path
- add reusable portal Q&A with global or company scope
- preview the complete generated `PROFILE.md`
- verify the current profile

All changes use the same validated atomic writer as onboarding.

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
5. Login, sign-up, registration, and create-account buttons are supported best-effort.
6. Unchecked terms/consent pause for manual review.
7. CAPTCHA always pauses for the user.
8. OTP is requested in the TUI, filled once, cleared from memory, and never persisted.

## 8. Field retrieval

For every form field:

```text
1. Exact structured PROFILE.md alias
   -> email, phone, first/last name, address, work authorization, SSN, etc.

2. Exact or similar reusable portal Q&A
   -> global answer or company-scoped answer

3. Non-sensitive local search / Agentic RAG
   -> professional summary, work history, projects, skills, insights, Q&A

4. Minimal-context agent reasoning
   -> LM Studio or OpenRouter after the agent adapter is implemented

5. Ask the user
   -> use once
   -> or save verified answer to PROFILE.md and reuse later
```

SSN and government-document values stop at step 1. They never enter RAG or any LLM prompt.

Low-confidence retrieval never fills automatically.

## 9. Fill and evidence

For each filled field:

1. Fill/select/check with Playwright.
2. Record field name and portal question.
3. Record profile source and confidence.
4. Store ordinary values; redact sensitive values and store only their hash.
5. Save an ordered event.
6. Capture a screenshot with password, OTP, SSN, passport, and license inputs blurred.
7. Save a browser checkpoint.

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

## 11. Supervised submit

Submission is disabled by default in Settings.

When enabled, all gates must pass:

1. verified profile
2. no unresolved answer, OTP, CAPTCHA, or consent
3. current preview hash
4. explicit user approval for that hash
5. active audited browser session
6. approval not previously consumed

The approval is atomically consumed before Playwright clicks Submit.

```text
confirmed page / URL change
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
      -> waiting_for_user_answer -> applying
      -> waiting_for_otp -> applying
      -> blocked_by_captcha -> applying
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
- Playwright login/account/OTP/inventory/fill/evidence foundation
- final review and supervised-submit gate
- automated profile, storage, gate, and TUI routing tests

## 15. Next hardening

- synthetic browser fixtures for login, sign-up, OTP, CAPTCHA, consent, multi-step forms, and confirmation
- persistent browser recovery after process restart
- LM Studio/OpenRouter agent adapter with schema validation
- disposable local vector index for non-sensitive profile chunks
- ATS-specific selectors and form adapters
- LaTeX/PDF build and document hashing

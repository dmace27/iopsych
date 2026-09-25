# IOPsych MVP: Technical Product Specification

## 1. MVP decision

Build a standalone web application for a **consented, human-reviewed pilot**. A recruiter creates a role from a job description, a hiring manager approves an editable role profile, a candidate completes a short work-preference assessment, and the recruiter receives an explainable interview-preparation report.

The MVP is deliberately not an ATS, résumé parser, candidate-ranking system, or automated decision maker. It must never reject, advance, rank, or otherwise make an employment decision. Its sole output is an evidence-seeking interview guide with visible uncertainty.

### In scope

- Recruiter, hiring-manager, candidate, and administrator accounts.
- Job-description input and structured LLM extraction.
- Editable and versioned role profiles.
- A short, versioned assessment covering six job-related constructs.
- Deterministic, per-construct matching with explanations.
- Recruiter report and generated interview prompts.
- Consent, audit events, basic data deletion, and accessibility support.

### Explicitly out of scope

- ATS integration, résumé parsing, online coding assessments, background checks, and production applicant ranking.
- Inferring personality, clinical state, protected traits, or protected-trait proxies.
- Machine-learning training on hiring outcomes.
- Automated interview scheduling, rejection, or advancement.
- Cross-company benchmarking or sharing candidate data between organizations.

## 2. Pilot assumptions and success criteria

Start with one internal or consented pilot role family, such as software engineering. Keep the first pilot to approximately 10–20 demo or consented candidates and 2–5 recruiters/hiring managers. Use synthetic candidate data until privacy, legal, and I-O psychology review are complete.

The MVP is successful when all of the following are true:

- A recruiter can create a role, obtain hiring-manager approval, invite a candidate, and access a report without engineering support.
- Candidate assessment median completion time is under 10 minutes.
- Every report signal links to specific assessment items or role-profile evidence.
- A report cannot be generated from an unapproved role profile.
- Recruiters can use the report to prepare a screen, but cannot record an automated disposition from it.
- A usability test shows that recruiters understand “worth discussing” does not mean “not qualified.”

## 3. User journeys

### 3.1 Recruiter: create and approve a role

1. Sign in and select **Create role**.
2. Enter title, department, location, and job-description text.
3. Submit the description for extraction.
4. Review LLM-proposed construct ratings, confidence, and quoted evidence.
5. Edit any rating and submit the profile to a hiring manager.
6. The hiring manager approves, requests edits, or rejects the draft.
7. After approval, invite a candidate by email link.

### 3.2 Candidate: consent and assessment

1. Open a single-use invite link.
2. Read purpose, data use, retention, accommodation, and contact information.
3. Provide affirmative consent or decline without penalty in the app.
4. Complete six forced-choice question blocks and optional context fields.
5. Review a plain-language completion screen; do not show a misleading “fit score.”
6. Optionally request a copy, correction, or deletion of their submitted data.

### 3.3 Recruiter: prepare an interview

1. Open the candidate report for an approved role version.
2. See six construct cards: role demand, candidate response, confidence, and classification.
3. Open evidence for any card.
4. Review one or two neutral behavioral questions for each “worth discussing” signal.
5. Record interview notes separately from the system-derived report.

## 4. Functional requirements

| ID | Requirement | Acceptance condition |
| --- | --- | --- |
| FR-01 | Role creation | Recruiter can save title, department, location, and job description. |
| FR-02 | Role extraction | The system returns schema-valid construct ratings, source excerpts, and confidence. |
| FR-03 | Human approval | Only a hiring manager can approve a role profile; reports use approved versions only. |
| FR-04 | Candidate consent | No questions are visible until the candidate consents; a decline is recorded. |
| FR-05 | Assessment | Candidate can complete, skip, return to, and submit six forced-choice blocks. |
| FR-06 | Matching | Submitted assessment plus approved role profile produces deterministic construct results. |
| FR-07 | Explainability | Each result includes role evidence, candidate response summary, rule, and uncertainty. |
| FR-08 | Interview guide | Each friction topic has a neutral, role-related behavioral prompt. |
| FR-09 | Auditability | Sensitive read and write actions generate immutable audit events. |
| FR-10 | Deletion | An administrator can export or delete a candidate’s MVP data by request. |

## 5. Construct model and assessment design

Use six constructs in version 1. Ratings are integers from 1 to 5, where 1 is low and 5 is high. All labels must be stated in behaviorally concrete language rather than diagnostic language.

| Key | Construct | Role rating asks | Candidate rating asks |
| --- | --- | --- | --- |
| `autonomy` | Autonomy | How independently the work must be organized | How strongly the candidate prefers self-direction |
| `structure` | Structure | How defined goals, routines, and requirements are | How strongly the candidate prefers predictable direction |
| `ambiguity` | Ambiguity tolerance | How often priorities/requirements are unclear or changing | How comfortable the candidate is acting amid uncertainty |
| `collaboration` | Collaboration | How much coordination, pairing, and stakeholder work the role needs | How much the candidate prefers collaborative work |
| `mastery` | Technical mastery | How much deep learning and complex problem solving the role offers | How energizing the candidate finds skill development and hard problems |
| `pace` | Pace/context switching | How often work requires urgency or shifting between priorities | How comfortable the candidate is with variety and shifting priorities |

### Assessment structure

Use six blocks of four balanced, work-preference statements. In every block, the candidate chooses one **most like me** and one **least like me** statement. Randomize statement order and balance construct exposure across the instrument. Include an accessible “prefer not to answer” option.

Example block:

| Statement | Construct |
| --- | --- |
| “I prefer to decide how I organize my workday.” | Autonomy |
| “I enjoy breaking down a technically difficult problem.” | Mastery |
| “I do my best work when goals and next steps are explicit.” | Structure |
| “I gain energy from developing ideas with teammates.” | Collaboration |

### Initial scoring rule

For each construct, assign `+1` when it is selected as most like the candidate and `-1` when selected as least like the candidate. Convert the aggregate to 1–5 using fixed, versioned thresholds after all blocks are complete. Store the raw choice data and scoring version; never overwrite historical scores.

The pilot should treat this as a usability instrument, not a validated psychometric test. Before operational use, a qualified I-O psychologist must evaluate content validity, reliability, adverse impact, candidate experience, and appropriate interpretation.

## 6. Role-extraction design

### Input

The extractor accepts only job-description text and role metadata. It must not receive a candidate résumé, name, demographic information, or prior hiring decision.

### LLM contract

Call an LLM with structured output constrained to this schema:

```json
{
  "constructs": [
    {
      "key": "autonomy",
      "rating": 4,
      "confidence": "medium",
      "rationale": "The role describes independent ownership of projects.",
      "evidence": ["Own technical direction for greenfield services."]
    }
  ],
  "assumptions": ["The job description may not describe team processes fully."],
  "needs_human_review": true
}
```

Validate the response with a server-side Pydantic schema. Reject extra fields, ratings outside 1–5, missing constructs, evidence not found in the submitted job description, or invalid confidence values. An extraction is always a draft; it cannot activate a role profile.

### Review UI

Show one editable card per construct with the rating, a low/medium/high confidence indicator, the extracted evidence, rationale, and a short definition. Save edits as a new profile version with `edited_by` and `edited_at`. Approval freezes that version for report generation.

## 7. Matching and interview-guide logic

Use an explainable rule engine—not a black-box classifier.

### Per-construct classification

Let `R` be the approved role rating and `C` be the candidate rating, both 1–5.

- **Aligned:** `abs(R - C) <= 1`, unless the construct is `structure`, where the role rating represents availability rather than demand; use the inverse `abs((6 - R) - C) <= 1`.
- **Worth discussing:** `abs(R - C) == 2`, using the same structure inversion.
- **Potential friction:** `abs(R - C) >= 3`, using the same structure inversion.
- **Insufficient evidence:** candidate skipped enough items or the role rating was not approved.

For `structure`, high role structure satisfies high candidate structure preference; a low role-structure rating means the role demands greater comfort with ambiguity. Store an explicit `comparison_target` in code so this interpretation is inspectable.

### Confidence

Candidate confidence is `high` when all assigned items are answered, `medium` when one item is skipped, and `low` when two or more are skipped. Role confidence comes from the approver’s selected confidence level. A report’s confidence is the lower of the two. Low-confidence signals should default to **insufficient evidence**, not a friction label.

### Interview-question library

Do not ask an LLM to invent questions in the critical path. Store a reviewed question library keyed by construct and classification. Select one primary question and one optional follow-up deterministically.

```text
construct=ambiguity, classification=potential_friction
primary: “Tell me about a time requirements were incomplete or changed quickly. How did you decide what to do next?”
follow_up: “What support, information, or routines helped you work effectively?”
```

An optional LLM can summarize already approved questions for tone, but may not create a new question without review.

## 8. System architecture

```text
Browser (Next.js)
        │ HTTPS / JSON
        ▼
API (FastAPI) ──> PostgreSQL
        │              │
        │              └── audit events, versioned data, encrypted secrets
        ├──> LLM structured extraction service
        └──> transactional email service for invite links
```

### Recommended technology choices

- **Web app:** Next.js, TypeScript, Tailwind CSS, React Hook Form, Zod, and Recharts.
- **API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, and Uvicorn.
- **Data:** PostgreSQL 16. Use UUID primary keys, UTC timestamps, and database migrations.
- **Authentication:** a vetted provider such as Clerk or Auth.js with magic-link or SSO support for internal users. Candidates use scoped, expiring invite tokens rather than full accounts.
- **Hosting:** Vercel for the web app plus a managed container platform for FastAPI and managed PostgreSQL, or deploy all services in one cloud environment. Store secrets in the hosting provider’s secret manager.
- **Observability:** structured JSON logs, error tracking, uptime checks, and a dashboard for extraction failures and report-generation latency.

## 9. Data model

Use the following initial relational model. PII should be limited to candidate email and display name, stored separately from assessment responses where practical.

```text
organizations 1─* users
organizations 1─* roles 1─* role_profiles 1─* role_construct_ratings
roles 1─* assessment_invites 1─0..1 candidate_assessments 1─* assessment_responses
candidate_assessments 1─* candidate_construct_scores
role_profiles + candidate_assessments 1─* alignment_reports 1─* alignment_items
organizations 1─* audit_events
```

Key tables and fields:

| Table | Essential fields |
| --- | --- |
| `users` | `id`, `organization_id`, `email`, `name`, `role`, `created_at` |
| `roles` | `id`, `organization_id`, `title`, `department`, `location`, `job_description`, `status` |
| `role_profiles` | `id`, `role_id`, `version`, `status`, `created_by`, `approved_by`, `approved_at` |
| `role_construct_ratings` | `profile_id`, `construct_key`, `rating`, `confidence`, `rationale`, `evidence_json` |
| `assessment_definitions` | `id`, `version`, `status`, `scoring_config_json` |
| `assessment_invites` | `id`, `role_profile_id`, `email`, `token_hash`, `expires_at`, `status` |
| `candidate_assessments` | `id`, `invite_id`, `definition_id`, `consented_at`, `submitted_at`, `candidate_note` |
| `assessment_responses` | `assessment_id`, `item_id`, `most_like_key`, `least_like_key`, `skipped_at` |
| `candidate_construct_scores` | `assessment_id`, `construct_key`, `rating`, `confidence`, `raw_score` |
| `alignment_reports` | `id`, `role_profile_id`, `assessment_id`, `generated_at`, `algorithm_version` |
| `alignment_items` | `report_id`, `construct_key`, `classification`, `confidence`, `explanation_json`, `question_ids` |
| `audit_events` | `id`, `actor_id`, `event_type`, `entity_type`, `entity_id`, `metadata_json`, `created_at` |

Never store raw invite tokens. Generate at least 32 random bytes, email the encoded token, and store only a cryptographic hash.

## 10. API surface

All internal endpoints require organization-scoped authentication and authorization. Candidate endpoints require only a valid, unexpired invite token. Return standard problem-detail errors and never expose data across organizations.

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/v1/roles` | Create a draft role |
| `POST` | `/v1/roles/{role_id}/extract-profile` | Generate a profile draft |
| `GET` | `/v1/roles/{role_id}/profiles/{profile_id}` | Read a profile version |
| `PATCH` | `/v1/roles/{role_id}/profiles/{profile_id}` | Edit a draft profile |
| `POST` | `/v1/roles/{role_id}/profiles/{profile_id}/approve` | Approve profile as hiring manager |
| `POST` | `/v1/roles/{role_id}/invites` | Create and email candidate invite |
| `GET` | `/v1/candidate/invites/{token}` | Read consent/assessment details |
| `POST` | `/v1/candidate/invites/{token}/consent` | Record consent or decline |
| `POST` | `/v1/candidate/invites/{token}/responses` | Save assessment progress |
| `POST` | `/v1/candidate/invites/{token}/submit` | Submit and calculate scores |
| `POST` | `/v1/reports` | Generate a report from approved profile + submitted assessment |
| `GET` | `/v1/reports/{report_id}` | Read recruiter report |
| `POST` | `/v1/candidates/{assessment_id}/export` | Create candidate data export |
| `DELETE` | `/v1/candidates/{assessment_id}` | Delete/anonymize data per policy |

## 11. Screens and components

1. **Sign-in and organization switcher** — internal users only.
2. **Roles list** — title, owner, profile status, invitations, and no candidate ranking.
3. **Create role** — metadata and job-description textarea with extraction progress.
4. **Role-profile review** — six editable construct cards, evidence, approval controls, version history.
5. **Invite candidate modal** — candidate email, expiry, purpose notice, and email preview.
6. **Candidate consent** — plain language, retention information, accommodations contact, accept/decline.
7. **Candidate assessment** — one block at a time, progress indicator, keyboard-friendly choices, save/return later.
8. **Completion page** — confirmation, data-rights links, no fit label.
9. **Recruiter report** — six comparison cards, evidence drawer, uncertainty markers, question guide, usage warning.
10. **Admin privacy view** — audit lookup, export request, deletion request, retention status.

## 12. Security, privacy, and accessibility baseline

- Enforce TLS, secure cookies, CSRF protection where needed, rate limiting, and content-security policy.
- Encrypt database storage and backups; use a managed secret store for credentials and API keys.
- Restrict database queries by `organization_id` at the service layer and verify it in every test suite.
- Use expiring candidate links, hashed invite tokens, one-time submission rules, and no assessment data in email bodies.
- Maintain a retention setting (default: short pilot period) and schedule deletion/anonymization after expiry.
- Provide a privacy notice, consent record, export/delete workflow, and accessibility/accommodation contact.
- Meet WCAG 2.2 AA basics: keyboard navigation, semantic headings, labels, focus states, non-color status indicators, contrast, and screen-reader announcements.
- Keep an immutable audit log for extraction, profile edits/approval, invite access, report access, exports, and deletions.

## 13. Delivery plan

### Step 0: Define the pilot (2–4 days)

1. Select a single role family and pilot organization.
2. Name the accountable product owner, I-O psychology advisor, privacy/legal reviewer, and engineering owner.
3. Write the candidate purpose statement, accommodation path, retention period, and human-review policy.
4. Define the six constructs and draft assessment items with an I-O psychology reviewer.
5. Confirm that the pilot will use synthetic or explicitly consented data.

**Exit condition:** Signed-off MVP scope and responsible-use constraints.

### Step 1: Product and design foundation (3–5 days)

1. Create user-flow diagrams and low-fidelity wireframes for the ten MVP screens.
2. Write exact empty, loading, error, consent, and uncertainty states.
3. Create a question library for every construct/classification combination.
4. Create example role descriptions, extraction results, candidate responses, and expected reports.
5. Conduct five usability walkthroughs with intended users using static designs.

**Exit condition:** Tested prototype and an agreed UI/content specification.

### Step 2: Repository and infrastructure (1–2 days)

1. Initialize a monorepo with `apps/web`, `apps/api`, and `packages/shared`.
2. Configure TypeScript, Python linting/formatting, pre-commit checks, environment templates, and CI.
3. Provision development PostgreSQL, object storage only if required, error monitoring, and secrets.
4. Create initial Alembic migration and seed fixtures.
5. Deploy a protected development environment and validate health checks.

**Exit condition:** A pull request can run lint, type checks, unit tests, and deploy a preview.

### Step 3: Internal-user workflows (5–7 days)

1. Implement authentication, organization scoping, and recruiter/hiring-manager roles.
2. Build roles list and create-role form with server validation.
3. Implement the role, profile, rating, and audit data model.
4. Implement the extraction endpoint against a mocked structured-response provider.
5. Build profile-review, edit, version, and approval flows.
6. Write authorization, API, and profile-version tests.

**Exit condition:** A manager-approved role profile is created end to end without candidate data.

### Step 4: Candidate workflow (4–6 days)

1. Implement secure invite-token generation, email delivery, expiry, and revocation.
2. Build candidate consent and decline flows.
3. Implement the versioned assessment renderer and draft-answer persistence.
4. Implement candidate score calculation with unit tests covering skips and versioning.
5. Build completion, export request, and deletion request flows.
6. Conduct keyboard and screen-reader testing of candidate screens.

**Exit condition:** A test candidate can complete the assessment securely and produce versioned construct scores.

### Step 5: Report and interview guide (3–5 days)

1. Implement matching rules as a pure, tested domain module.
2. Build report generation restricted to approved role profiles and submitted assessments.
3. Build recruiter comparison cards, evidence drawer, and uncertainty display.
4. Connect the reviewed interview-question library.
5. Add usage warning and audit logging for report views.

**Exit condition:** Every report item has traceable inputs and at least one appropriate interview question.

### Step 6: LLM, security, and quality hardening (3–5 days)

1. Replace the mocked extractor with structured LLM output.
2. Add schema, evidence-string, and rating validation; handle provider retries and failures safely.
3. Conduct threat modeling for roles, invite tokens, authorization, PII, and prompt injection.
4. Add rate limits, CSP, security headers, audit review, backup verification, and logging redaction.
5. Run accessibility audit, integration tests, and end-to-end tests.

**Exit condition:** The app meets MVP security, privacy, accessibility, and reliability acceptance checks.

### Step 7: Pilot readiness and launch (2–3 days)

1. Seed demo roles and synthetic candidates for training.
2. Train pilot users on responsible interpretation and interview use.
3. Publish support, incident, data-rights, and rollback procedures.
4. Run a controlled end-to-end rehearsal.
5. Start with a small invitation batch and monitor completion, errors, and user feedback daily.

**Exit condition:** Pilot owner approves launch; all participants can access support and privacy materials.

## 14. Testing strategy

| Layer | What to test |
| --- | --- |
| Unit | Assessment scoring, comparison targets, classification boundaries, confidence rules, token hashing |
| API | Authentication, tenant isolation, approval gates, consent gate, validation failures, audit creation |
| Integration | Database migrations, LLM schema validation, email invite lifecycle, report persistence |
| End-to-end | Recruiter role creation through candidate completion and report viewing |
| Accessibility | Keyboard-only assessment, focus order, screen-reader labels, color contrast, error messages |
| Security | Expired/revoked token behavior, IDOR/tenant-isolation attempts, rate limiting, logging redaction |
| Human factors | Recruiter interpretation, candidate comprehension, assessment timing, question relevance |

Required fixtures include: an approved high-autonomy role; a low-structure role; a candidate with complete responses; a partially skipped assessment; an unapproved profile; an expired invite; and two organizations to test access boundaries.

## 15. Metrics and pilot review

Track operational metrics without using them as hiring metrics:

- Role-profile extraction success rate and manager edit rate by construct.
- Time from role creation to approved profile.
- Invite delivery and assessment completion rates.
- Assessment completion time and skip rate.
- Percentage of low-confidence/insufficient-evidence items.
- Report-generation error rate and latency.
- Recruiter usefulness rating and candidate clarity rating.
- Privacy requests, accessibility issues, and incident count.

At pilot end, review all results with the I-O, privacy, and product owners. Decide whether to refine the user experience, validate the assessment more formally, extend the role family, or stop the pilot. Do not expand to employment decisions based only on favorable engagement metrics.

## 16. Launch checklist

- [ ] Scope explicitly excludes automated employment decisions.
- [ ] Assessment items and candidate text have I-O psychology review.
- [ ] Privacy notice, consent language, retention period, and accommodation route are approved.
- [ ] Role profile requires documented human approval.
- [ ] Reports cannot be generated from unapproved profiles or unconsented assessments.
- [ ] Every report label includes evidence, a rule explanation, and confidence.
- [ ] Candidate token, organization scoping, and authorization tests pass.
- [ ] Audit events are present for all sensitive actions.
- [ ] Accessibility and security checks pass.
- [ ] Synthetic end-to-end rehearsal passes.
- [ ] Pilot users have received interpretation training and support contacts.

## 17. Agent-ready implementation plan

Use the phases below as hand-off packages. Within a phase, agents may work in parallel only when the table says they can. Begin the next phase after the listed dependencies and acceptance checks are complete. One lead agent should own integration, schema/API contract changes, and final review; individual agents should avoid opportunistic refactors outside their assigned package.

### Shared working agreement

- Read this specification before making changes and preserve the no-automated-decision boundary.
- Make each package independently testable; add or update tests with the implementation.
- Keep contracts versioned and documented. Flag a proposed schema or API change before implementing it.
- Do not use real candidate information in fixtures, logs, screenshots, or tests.
- Each hand-off must include changed files, commands run, test results, open risks, and any follow-up work.

### Phase 0: Foundations and contracts

Run these packages first. They establish the interfaces all later work depends on.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 0A — Technical foundation | Initialize the monorepo, `apps/web`, `apps/api`, and `packages/shared`; add formatting, linting, type checks, test runners, environment templates, CI, and health endpoints. | None | A clean clone can install dependencies, run both apps locally, and execute CI checks. |
| 0B — Domain contract | Define the six construct keys, enums, JSON/Pydantic/TypeScript schemas, scoring-config shape, API error format, and fixture conventions in one shared contract package. | 0A | API and frontend can import the same construct definitions; contract validation tests pass. |
| 0C — Data foundation | Configure PostgreSQL, SQLAlchemy/Alembic, database settings, base models, UTC/UUID conventions, and a seed command. Create migrations for organizations, users, roles, profiles, ratings, and audit events. | 0A, 0B | Migrations apply to an empty database and seed two isolated organizations with no cross-tenant access. |

**Recommended hand-off prompts**

- **0A:** “Set up the IOPsych MVP monorepo and developer tooling described in `mvp-spec.md` section 17, package 0A. Do not add product features. Document run/test commands.”
- **0B:** “Implement the shared domain contracts in `mvp-spec.md` section 17, package 0B. Keep construct semantics and validation aligned with sections 5–7.”
- **0C:** “Implement the database foundation in `mvp-spec.md` section 17, package 0C. Use the data model in section 9 and include tenant-isolation fixtures/tests.”

### Phase 1: Internal role-profile workflow

These packages create the recruiter and hiring-manager path. Complete authentication before the role/profile API, then integrate the UI.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 1A — Auth and authorization | Add internal-user authentication, organization scoping, recruiter/hiring-manager/admin roles, authorization helpers, and audit middleware. | Phase 0 | Unauthorized and cross-organization requests are rejected; sensitive actions emit audit events. |
| 1B — Role/profile API | Implement role CRUD, profile drafts, construct-rating edits, immutable versions, and hiring-manager approval. Enforce that approved versions cannot be edited. | 0B, 0C, 1A | API tests show a profile can be drafted, versioned, approved, and cannot be mutated afterward. |
| 1C — Role/profile UI | Build the roles list, role creation form, profile-review cards, evidence display, version history, and approval controls against the defined API. Use fixture data until 1B is available. | 0B; integrate with 1B | A recruiter can create a role and a hiring manager can review/edit/approve it in the browser. |

**Recommended hand-off prompts**

- **1A:** “Implement package 1A from the agent-ready plan. Focus only on authentication, RBAC, organization isolation, and audit middleware; provide authorization tests.”
- **1B:** “Implement package 1B from the agent-ready plan. Build the role and versioned-profile API, including the approval gate. Do not implement candidate functionality.”
- **1C:** “Implement package 1C from the agent-ready plan. Build the internal role and profile screens with accessible states. Use existing contracts and avoid changing backend interfaces without approval.”

### Phase 2: Candidate assessment foundation

Run 2A and 2B in parallel after Phase 1’s contracts are stable; 2C integrates them.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 2A — Assessment domain | Create versioned assessment definitions, question blocks, reviewed question fixtures, response persistence, deterministic scoring, skips, and construct-score confidence calculation. | 0B, 0C | Unit tests cover every scoring threshold, skipped response, and scoring-version persistence. |
| 2B — Invite and consent API | Implement signed/hashed expiring invite tokens, delivery adapter interface, revocation, consent/decline recording, and rate limits. | 0C, 1A, 1B | Tokens are hashed at rest; expired/revoked/other-organization access fails; no assessment starts without consent. |
| 2C — Candidate experience | Build the email-link landing page, consent flow, accessible assessment renderer, save/resume behavior, completion view, and clear data-rights link. | 2A, 2B | A synthetic candidate completes an assessment using only a keyboard; result data persists without exposing a fit score. |

**Recommended hand-off prompts**

- **2A:** “Implement package 2A from `mvp-spec.md`: the versioned assessment domain and deterministic scoring. Keep it pure and thoroughly unit-tested.”
- **2B:** “Implement package 2B from `mvp-spec.md`: secure candidate invitations and consent endpoints. Do not store raw tokens or send assessment data in email.”
- **2C:** “Implement package 2C from `mvp-spec.md`: the accessible candidate consent and assessment UI. Respect the API contracts and test keyboard flow.”

### Phase 3: Explainable report workflow

The matching engine must be completed and reviewed before the recruiter report is connected to it.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 3A — Matching engine | Implement a pure domain module for role/candidate comparisons, confidence rules, classifications, explanation payloads, and approved interview-question selection. | 0B, 1B, 2A | Boundary tests cover all constructs, including the inverse structure rule, low-confidence behavior, and unapproved profiles. |
| 3B — Report API | Persist report and report-item records; permit generation only for submitted, consented assessments and approved role-profile versions; add report access audits. | 3A, 1A, 1B, 2B | API response contains traceable evidence, rule explanation, confidence, and question IDs for each item. |
| 3C — Recruiter report UI | Build the construct comparison cards, evidence drawer, uncertainty states, interview guide, and responsible-use warning. | 3B | Recruiter can read an accessible report with no hidden composite or candidate ranking. |

**Recommended hand-off prompts**

- **3A:** “Implement package 3A from the agent-ready plan. Deliver the matching engine as a pure, documented module with comprehensive boundary tests; do not introduce a hire score.”
- **3B:** “Implement package 3B from the agent-ready plan. Build the guarded, audited report-generation API using the matching module exactly as specified.”
- **3C:** “Implement package 3C from the agent-ready plan. Build the recruiter report UI emphasizing evidence, uncertainty, and interview preparation—not a decision recommendation.”

### Phase 4: Structured extraction and privacy controls

Package 4A can begin once role profiles work; package 4B needs the candidate workflow; package 4C needs reports. They are not allowed to relax any approval or candidate-consent gate.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 4A — Structured role extraction | Integrate the LLM provider behind an interface; enforce structured output, Pydantic validation, source-evidence matching, retries, failure states, and draft-only status. | 0B, 1B | Bad/missing schema values and unsupported evidence are rejected; successful output still requires human approval. |
| 4B — Data rights and retention | Implement candidate export, deletion/anonymization, retention configuration/job, audit history, and admin privacy screens. | 0C, 1A, 2B, 2A | An admin can complete export and deletion requests; retention behavior is tested and auditable. |
| 4C — Security hardening | Add security headers, rate limits, CSRF/session protections, log redaction, secrets checks, and dependency scanning. Threat-model role/profile, report, and token flows. | 1A, 2B, 3B | Threat-model actions are resolved or explicitly accepted; security checks run in CI. |

**Recommended hand-off prompts**

- **4A:** “Implement package 4A from `mvp-spec.md`. Add structured LLM extraction only; validate every field and preserve the mandatory human-approval gate.”
- **4B:** “Implement package 4B from `mvp-spec.md`. Build data-rights and retention controls with auditable, tested flows.”
- **4C:** “Implement package 4C from `mvp-spec.md`. Harden the existing MVP without expanding product scope; provide the threat model and CI evidence.”

### Phase 5: Integration, quality, and pilot release

Use these as final, sequential packages. The lead agent should review all changes before handing over the pilot build.

| Package | Agent task | Depends on | Done when |
| --- | --- | --- | --- |
| 5A — End-to-end quality | Add complete E2E tests for role-to-report flow, negative authorization/consent/approval paths, fixture seeding, and a reliable local test environment. | Phases 1–4 | CI runs the full happy path and required failure paths against isolated test data. |
| 5B — Accessibility and UX audit | Test keyboard, screen reader, focus management, color contrast, copy clarity, errors, and responsive layout across all MVP screens. Fix all blocking issues. | Phases 1–4 | WCAG 2.2 AA baseline checklist is documented and blocking issues are resolved. |
| 5C — Pilot operations | Write deployment, rollback, support, incident, user-training, data-rights, and release-checklist documents; run a synthetic rehearsal. | 5A, 5B | The launch checklist in section 16 is complete and a rehearsal is documented. |

**Recommended hand-off prompts**

- **5A:** “Implement package 5A from the agent-ready plan. Add stable end-to-end coverage for the entire MVP and all required negative paths.”
- **5B:** “Implement package 5B from the agent-ready plan. Audit and fix accessibility/usability gaps across the complete app; document evidence.”
- **5C:** “Implement package 5C from the agent-ready plan. Produce pilot runbooks and complete a synthetic end-to-end release rehearsal; do not use real candidate data.”

### Suggested delegation order

```text
Phase 0:  0A ──> 0B ──> 0C
Phase 1:  1A ──> 1B ──> 1C
Phase 2:  2A + 2B ──> 2C
Phase 3:  3A ──> 3B ──> 3C
Phase 4:  4A (after 1B); 4B (after 2B); 4C (after 3B)
Phase 5:  5A ──> 5B ──> 5C
```

The lead agent should merge and verify each phase before beginning the next. This avoids conflicting database/API changes while still allowing parallel work where boundaries are clear. yes


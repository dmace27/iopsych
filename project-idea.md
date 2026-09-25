# IOPsych: Explainable Role-Alignment for Recruiting

## Project summary

IOPsych is a recruiter decision-support application that adds structured, job-relevant context to an applicant profile before a screening interview. Rather than treating a résumé keyword match as a proxy for suitability, it compares the day-to-day realities of a role with a candidate's stated work preferences and behavioral tendencies.

The product identifies two kinds of signals:

- **Drivers:** conditions that tend to energize and engage someone, such as autonomy, technical mastery, collaboration, recognition, or predictable goals.
- **Depressors:** conditions that can create friction or drain energy, such as micromanagement, ambiguity, isolation, bureaucracy, or frequent context switching.

Its purpose is to help a recruiter prepare a more relevant, evidence-seeking conversation—not to determine whether a person should be hired. The output is an explainable alignment profile, specific areas to probe in an interview, and candidate-visible context about how the assessment will be used.

## Problem

Technical recruiting funnels are highly automated. Applicant Tracking Systems (ATSs) commonly score résumés against skills, job titles, and eligibility questions, then may automatically send online assessments or rank candidates. These signals can be efficient, but they say little about whether a candidate will find a particular work environment sustainable and motivating.

Recruiters need a lightweight way to understand:

1. What demands and working conditions a role actually contains.
2. Which conditions a candidate prefers or finds draining.
3. Where those profiles align and where a structured interview should gather more evidence.

## Users and core value

| User | Need | Value from IOPsych |
| --- | --- | --- |
| Recruiter | Prepare a focused screen quickly | An explained fit profile and targeted interview prompts |
| Hiring manager | Communicate the real operating environment of the team | A structured role profile they can review and correct |
| Candidate | Understand what the job will be like and discuss preferences fairly | Transparent assessment, consent, and a chance to add context |
| People/IO team | Use a consistent, auditable process | Versioned constructs, score explanations, and outcome monitoring |

## MVP workflow

1. A recruiter creates a role and pastes in a job description.
2. An LLM extracts a draft role profile from the job description: role demands, likely drivers, potential depressors, and evidence for each inference.
3. The recruiter or hiring manager reviews and edits that profile; the human-approved version is the only profile used for matching.
4. A candidate completes a brief, accessible work-preference assessment—ideally 10 minutes or less.
5. The matching engine compares the candidate and role profiles by construct and produces clear alignment, friction, and uncertainty signals.
6. The recruiter sees an interview cheat sheet with neutral questions tailored to the role-candidate gaps.
7. The candidate can see what was collected, how it is used, and provide optional context or request review.

## Product experience

### Role profile

The role profile should turn unstructured job-description language into editable ratings on a small, stable set of constructs. For example, a description that emphasizes independent greenfield work with changing priorities might be drafted as high autonomy and high ambiguity tolerance, while indicating that a strong need for fixed structure could be a potential friction point.

Each inferred rating must include:

- a rating and confidence level;
- the exact job-description evidence used to make the inference;
- the hiring manager's edits and approval status;
- a version history, so historical comparisons remain interpretable.

### Candidate assessment

Use short, job-related situational judgment and forced-choice questions instead of an opaque personality test. A forced-choice item can ask a candidate to select the statement most like them and least like them from a balanced set such as autonomy, mastery, structure, and collaboration preferences.

The assessment should avoid clinical claims, diagnoses, emotion recognition, or inferences about protected characteristics. Candidates should be able to skip questions, provide contextual notes, and receive a plain-language explanation of the result.

### Recruiter dashboard

The dashboard should not present a single “hire score.” It should show:

- a construct-by-construct comparison between the role and candidate;
- strengths where the role is likely to satisfy a candidate driver;
- potential friction where a role demand conflicts with a candidate preference;
- uncertainty and missing data;
- a structured interview guide for confirming or challenging each signal.

Example: if the candidate reports a high preference for structure and the approved role profile requires navigating ambiguity, the dashboard flags an interview topic—not a rejection. It could suggest: “Tell me about a time you entered a project with incomplete requirements. How did you establish priorities and decide what to do next?”

## Alignment model

Start with a deliberately small, interpretable construct set:

| Construct | Role signal | Candidate signal | Interpretation |
| --- | --- | --- | --- |
| Autonomy | Degree of independent ownership required | Preference for self-direction | Potential driver alignment |
| Structure | Clarity, routines, and defined goals in the role | Preference for predictability | Possible friction if needs differ |
| Ambiguity tolerance | Frequency of unclear requirements or changing priorities | Comfort operating without certainty | Role-demand fit to validate |
| Collaboration | Coordination, pairing, and stakeholder interaction | Preference for team-based work | Work-style alignment |
| Mastery | Depth of technical/problem-solving challenge | Motivation from learning and difficult problems | Engagement opportunity |
| Pace/context switching | Urgency and number of competing demands | Preference for variety versus focus | Workload and burnout-risk discussion |

Represent both profiles as normalized vectors with a score and confidence for each construct. For a first version, use transparent per-construct gap rules and a weighted distance calculation rather than an opaque machine-learning model. The system can express results as **aligned**, **worth discussing**, or **insufficient evidence**. Scores must always link back to assessment responses or approved job-profile evidence.

Do not use a composite score as a hiring cutoff. If a summary is needed for navigation, label it as an **interview-prioritization signal** and expose its components and limitations.

## Technical architecture

```text
Job description ──> LLM extraction ──> Human-reviewed role profile
                                                    │
Candidate assessment ──> Candidate trait profile ──┤
                                                    ▼
                                          Explainable matching engine
                                                    ▼
                                Recruiter dashboard + interview guide
```

Suggested MVP stack:

- **Frontend:** Next.js, TypeScript, Tailwind CSS, and Recharts for comparison charts.
- **Backend:** Python with FastAPI, chosen for straightforward data validation and analytics workflows.
- **Database:** PostgreSQL for roles, assessment versions, profiles, consent records, audit events, and interview outputs.
- **AI extraction:** An LLM with structured JSON output and schema validation. Store the source snippets and confidence, then require human approval before a role profile is active.
- **Authentication and authorization:** Role-based access for recruiters, hiring managers, candidates, and administrators.

## Core data entities

- `Role`: title, department, location, job description, owner, status.
- `RoleProfile`: role ID, construct ratings, source evidence, reviewer edits, version, approval metadata.
- `AssessmentDefinition`: question set, construct mapping, scoring method, version, validation status.
- `CandidateAssessment`: candidate ID, consent, responses, calculated construct ratings, confidence, optional comments.
- `AlignmentReport`: role-profile version, assessment version, construct comparisons, explanation text, uncertainty, generated interview prompts.
- `AuditEvent`: viewer, action, timestamp, report version, and any decision or override note.

## Responsible-use requirements

Hiring is a high-impact domain. The MVP must be designed as a decision-support system with human review, not an automated employment decision system.

- Never auto-reject, rank, or advance candidates solely using assessment or alignment results.
- Do not infer or use protected traits, health information, disability, age, race, religion, gender identity, sexual orientation, nationality, or proxies for them.
- Provide informed consent, a clear purpose statement, retention/deletion rules, and a reasonable accommodation path.
- Give candidates understandable feedback and a way to correct context or request review.
- Log profile edits, access, score generation, and human decision rationales.
- Test for disparate impact and measurement bias before using results operationally; engage qualified I-O psychology and legal/privacy reviewers.
- Treat LLM output as a draft, validate structured data, and require human approval of job-demand inferences.

## Build plan

### Phase 1: Clickable, explainable prototype

Build a role-entry screen, a mock candidate assessment, an editable role-profile view, and a recruiter dashboard powered by fixture data. Validate whether recruiters understand the output and whether hiring managers agree with the inferred role demands.

### Phase 2: Functional MVP

Add authentication, PostgreSQL storage, structured LLM extraction, versioned assessment scoring, human approval, consent capture, and interview-guide generation. Keep the model rule-based and fully explainable.

### Phase 3: Validation and pilot

Run a small, consented pilot with a defined role family. Evaluate completion rate, recruiter usefulness, hiring-manager agreement with role profiles, candidate experience, reliability of the constructs, and fairness across relevant groups where lawful and appropriate. Do not optimize against hiring outcomes until the measure has been professionally validated.

### Phase 4: ATS integration

Integrate with ATS platforms such as Greenhouse, Lever, or Ashby only after the standalone workflow is trustworthy. Sync profiles and interview guides as supplemental context, preserve audit trails, and ensure the integration cannot trigger automated rejection actions.

## Definition of success for the MVP

The first release succeeds if a recruiter can turn a job description into a manager-approved role profile, invite a candidate to a short transparent assessment, and receive an interpretable interview guide within minutes. The system should make screening conversations more specific and fairer without creating a hidden “fit” gate.

## Open decisions

1. Which initial role family will the tool serve (for example, engineering, customer success, or operations)?
2. Which constructs are supported by the assessment, and what validation evidence is required before use?
3. What jurisdiction, retention period, accessibility standard, and consent language apply to the pilot?
4. Will the first release use synthetic/demo candidates only, or a consented internal pilot?

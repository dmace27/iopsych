# Shared contracts

Version 1 domain contracts for the IOPsych web and API workspaces. The package
exposes equivalent Zod/TypeScript and Pydantic representations, generated JSON
Schema documents, and one synthetic fixture suite exercised by both languages.
The canonical construct metadata is checked in at
`definitions/v1/constructs.json`; parity tests prevent either runtime from
drifting from it.

## Contract surface

- The six construct keys and behaviorally worded labels/prompts
- Confidence, comparison-target, and alignment-classification enums
- Strict role-extraction validation, including source-evidence checks
- Versioned forced-choice scoring configuration shape
- Versioned six-block assessment definitions and save/resume response snapshots
- Pure deterministic per-construct scoring with explicit skip confidence
- Pure deterministic role/candidate matching with evidence explanations
- A versioned, approved interview-question library with stable question IDs
- Definition and scoring version stamps on every score result
- RFC 9457-compatible API problem details

The synthetic pilot definition is checked in at
`definitions/v1/pilot-assessment.json`. It is intentionally marked `draft`: its
content supports integration testing but must receive the I-O psychology review
required by `mvp-spec.md` before an application publishes it to candidates.
Assessment definition lifecycle status does not affect pure scoring, because
responses tied to a retired version must remain reproducible.

The `structure` definition records `inverse_role_rating`, following the explicit
formula and package 3A acceptance text in `mvp-spec.md` section 7. The matching
engine therefore uses `6 - role_rating` as the structure comparison target and
includes that target in every explanation. The prose immediately following the
formula is internally inconsistent and should still be reconciled by the domain
owner before pilot use.

## Usage

TypeScript consumers import from the workspace package:

```ts
import { CONSTRUCT_KEYS, RoleExtractionSchema } from "@iopsych/shared";
```

Score only complete response snapshots; drafts may omit blocks for save/resume,
while a candidate's “prefer not to answer” choice is stored as an explicit skip:

```ts
import {
  PILOT_ASSESSMENT_DEFINITION_V1,
  scoreAssessment,
} from "@iopsych/shared";

const result = scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet);
// Persist result.assessment_definition_version and result.scoring_version.
```

Match only against a role snapshot whose approval state is supplied explicitly:

```ts
import { matchRoleProfile } from "@iopsych/shared";

const result = matchRoleProfile(roleProfile, assessmentScoreResult);
```

`matchRoleProfile` returns six independent construct items in canonical order.
Each item contains the role evidence, candidate response summary, comparison
target, absolute-difference rule, combined confidence, uncertainty, and one
approved primary/follow-up question pair. Low confidence or an unapproved role
profile yields `insufficient_evidence`. The module performs no I/O, uses no
randomness, mutates neither input, and exposes no aggregate or hire score.

The reviewed question content is checked in at
`definitions/v1/interview-questions.json`. Question IDs and
`MATCHING_ALGORITHM_VERSION` must be versioned when behavior or wording changes;
historical reports should retain the exact IDs and algorithm version they used.

The repository setup installs the Python package in editable mode:

```python
from iopsych_contracts import CONSTRUCT_KEYS, RoleExtraction
```

Regenerate checked-in JSON Schema documents after a Zod contract change:

```bash
npm run schemas --workspace @iopsych/shared
```

`npm test` verifies the checked-in schemas are synchronized and applies the
shared fixtures to both Zod and Pydantic. See
[`fixtures/README.md`](./fixtures/README.md) before adding fixture data.

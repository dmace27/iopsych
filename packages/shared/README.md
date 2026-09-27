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
- Definition and scoring version stamps on every score result
- RFC 9457-compatible API problem details

The synthetic pilot definition is checked in at
`definitions/v1/pilot-assessment.json`. It is intentionally marked `draft`: its
content supports integration testing but must receive the I-O psychology review
required by `mvp-spec.md` before an application publishes it to candidates.
Assessment definition lifecycle status does not affect pure scoring, because
responses tied to a retired version must remain reproducible.

The `structure` definition records `inverse_role_rating`, following the explicit
formula and package 3A acceptance text in `mvp-spec.md` section 7. This makes
the exceptional comparison rule visible to later matching code. The prose
immediately following that formula is internally inconsistent and should receive
domain-owner review before package 3A is implemented.

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

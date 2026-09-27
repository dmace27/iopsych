# IOPsych Python contracts

Pydantic representation of the version 1 shared domain contracts. The repository
setup script installs this package in editable mode for the FastAPI application.

The package also exposes the pure assessment scorer used by the API boundary:

```python
from iopsych_contracts import score_assessment

result = score_assessment(definition, response_set)
```

The score result retains both the assessment-definition version and the scoring
version. Response snapshots may be partial for save/resume; scoring requires one
answer or explicit skip for every block.

The package also exposes the pure Package 3A matcher:

```python
from iopsych_contracts import match_role_profile

result = match_role_profile(role_profile, assessment_score_result)
```

The result contains six independent, evidence-linked classifications and stable
interview-question IDs. Low-confidence evidence and unapproved role profiles
fail closed to `insufficient_evidence`. No aggregate, ranking, recommendation,
or hire score is produced.

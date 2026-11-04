# Structure comparison policy

Product decision confirmed by the repository owner on November 3, 2026: compare
the role's available structure directly with the candidate's preference for
predictable direction. This records a product interpretation; independent I/O
psychology review remains part of the real-pilot approval in Task 16.

## Meaning of the scales

The role scale measures available structure: 1 means largely undefined goals,
routines, and requirements; 5 means clearly defined goals, routines, and
requirements. The candidate scale measures preference for predictable direction:
1 means a low preference; 5 means a strong preference.

Algorithm `2.0.0` uses `abs(role_rating - candidate_rating)` for structure and
records `comparison_target: role_rating`. The existing distance boundaries,
approval gate, and confidence gate apply. Low confidence or an unapproved
profile still produces `insufficient_evidence`.

| Role structure | Candidate preference | Outcome with sufficient evidence | Meaning                                                           |
| -------------- | -------------------- | -------------------------------- | ----------------------------------------------------------------- |
| 5              | 5                    | Aligned                          | Clearly defined work meets a strong preference for direction.     |
| 1              | 1                    | Aligned                          | Little predefined process matches a low preference for direction. |
| 1              | 5                    | Potential friction               | Available direction is lower than the candidate prefers.          |
| 5              | 1                    | Potential friction               | Available process is greater than the candidate prefers.          |

These symmetric distance rules identify interview topics. They are not a
validated prediction of performance or a hiring recommendation. Structure and
ambiguity remain separate constructs; neither rating determines the other.

## Version and historical-data policy

- New generation uses matching algorithm `2.0.0` in both languages.
- Algorithm `1.0.0` retains the old inverse structure target, `6 - role_rating`,
  for explicit replay. Its frozen fixture must reproduce exactly.
- Report readers accept both supported versions and reject unknown versions or a
  comparison target that disagrees with the declared algorithm. Reading a report
  returns the saved result, questions, and explanation without scoring or
  matching again.
- Current metadata lives in `packages/shared/definitions/v2/constructs.json`.
  The original v1 metadata and question library remain unchanged. The serialized
  contract shape stays at version 1; its compatible reader schema now supports
  both algorithm versions.
- Report discovery prefers v2 if present, otherwise v1. Explicit generation of a
  v2 report creates a separate record; repeat generation is idempotent for that
  input/algorithm combination. Existing v1 rows are not rewritten.
- The UI labels the role value as available structure and explains the direct v2
  comparison. Historical v1 reports explicitly identify the original inverse
  comparison and keep its classifications and questions.

Task 7's remaining assessment-definition assignment and lifecycle work must be
completed before deployment over existing candidate data. This change does not
record deployment approval or scientific validation.

## Verification

Both runtime suites consume the same four meaning-based examples. A frozen v1
result checks complete cross-language replay and historical parsing. API tests
exercise saved-v1 reads, v1 discovery, separate v2 generation, idempotency,
discovery with both versions present, and unchanged v1 storage. Browser
component tests cover direct v2 wording and preserved v1 wording and questions.

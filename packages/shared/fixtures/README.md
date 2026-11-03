# Contract fixture conventions

Fixtures are versioned with the serialized contracts under `fixtures/v1`. Every
JSON case contains:

- `contract`: the validator to use;
- `expected_valid`: the expected outcome;
- `payload`: the serialized value under test;
- `context`: only when validation needs trusted external context, such as the
  submitted job description used to verify extraction evidence.

Fixtures must be synthetic, contain no candidate or employee information, and
exercise one meaningful contract rule. A future breaking contract must use a new
version folder; existing fixture meanings must not be silently changed.

The scoring thresholds in these fixtures exist only to test the configuration
shape. They are not reviewed assessment policy and must not be used as a
production scoring definition.

`v1/matching-result/legacy-structure.json` freezes a complete result from the
original algorithm, with synthetic inputs for exact cross-language replay. Keep
that payload unchanged when the current matcher changes.
`v2/matching/structure-extremes.json` contains four meaning-based structure
comparison cases under `contract: structure_comparison_cases`; both language
suites check those same expected classifications and differences.

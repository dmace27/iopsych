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

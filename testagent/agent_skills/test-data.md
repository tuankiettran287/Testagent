# Rule-derived test data

## Deliverable and inputs

Return AgentAnalysis containing a small useful data matrix for the requested feature. Use real supplied rules/schemas/code or observed constraints. Do not invent authorized identities, tokens or production records.

## Procedure

1. Identify field type, required/nullability, enum, length/range/format, uniqueness and cross-field constraints. Label unknown or conflicting rules.
2. Select representative applicable classes: valid, omitted, null, empty, boundary, just outside, malformed, relevant Unicode/whitespace. These are distinct only when the interface makes them distinct.
3. For an evidenced inclusive numeric range [m, M], consider m-1, m, an interior value, M and M+1. Without a known range, ask for it rather than inventing thresholds.
4. Connect every value to a purpose and expected-result basis. Intentional invalid synthetic values are test inputs, not authorized login credentials.
5. Combine interacting fields; propose pairwise reduction for independent dimensions without claiming a tool already generated/executed it.
6. Define concrete actor/tenant/resource setup, uniqueness/reuse and restoration needs. Browser reset does not reset server records.
7. Check implementability: literal actions do not expand worker/UUID/token placeholders; the runner has no fixture seeding or token capture.

## Output quality

Findings uses existing detail fields to describe field/rule, representative values, oracle, setup and uncertainty. Cite supporting supplied IDs; do not add a custom data schema to AgentAnalysis.

recommendations prioritizes missing constraints and fixture preparation, with parallel suitability. Use precise literals without secrets/personal records in explanations.

## Completion and handoff

Each proposed row has a discriminating purpose, explicit dependency and reproducible expected basis. Hand values to case design or automation_builder; keep unresolved fixtures manual and avoid broad document requests or claims that data has been created.

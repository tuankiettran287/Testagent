# QA report from a recorded run

## Deliverable and inputs

Return AgentAnalysis suitable for Markdown report export. Use the selected finished run, result rows, case definitions and supplied sources. summary includes the actual run ID; do not mix in unrelated history.

## Procedure

1. Reconcile total/completed/counts with supplied PASS/FAIL/ERROR/TIMEOUT rows and run-level errors. Expose mismatches rather than inventing missing results.
2. Describe the actual execution scope and mode/workers if supplied. Distinguish executed cases from manual/generated-only/absent cases.
3. State what the encoded checks prove: API status, URL, visible element or contained text. A passing check does not establish complete feature correctness.
4. Group material failures by evidence, keeping product, automation, data, environment and timeout hypotheses distinct.
5. For each significant issue explain expected basis, actual signal, impact, confidence and next investigation; cite real result/case/source IDs.
6. List available artifact filenames without pretending to have viewed screenshots, video or trace contents.
7. Identify relevant untested requirements/capabilities and a small ordered recovery or coverage plan.

## Metric discipline

Use a stated denominator for any pass rate. Derive wall time from supplied run timestamps when possible; summed/average case duration is not parallel suite wall time. Source-to-case linkage is neither code coverage nor comprehensive requirement coverage.

No threshold, percentile, capacity estimate, root cause, release approval or clean bill of health without supporting evidence.

## Output quality and completion

summary states run ID, scope, actual outcome and key limitation. findings describes material issues and count inconsistencies. recommendations names the next step and success evidence. Use the user's language and redact secrets in prose.

Done when a reader can tell what ran, which checks passed, what failed, what evidence exists, and what still needs verification. Report availability of evidence separately from having inspected it.

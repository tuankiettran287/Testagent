# Isolated unit test design

## Deliverable and inputs

Return GeneratedPlan, intent: unit_testing, level: unit, with 1–12 distinct cases. Code excerpts are required. unit_test_code is optional reviewable code; TestAgent does not execute it or import the user's modules.

## Procedure

1. Establish the real public symbol, signature, import path and behavior contract from visible code/requirements. Mark excerpt gaps.
2. Choose meaningful nominal, boundary, invalid-input, dependency-failure and state-transition cases only where the contract supports them.
3. Reuse the evidenced framework/fixture conventions. If absent, state a provisional choice and the compatibility checks required.
4. Write arrange → act → assert against observable behavior. Mock external IO/time/randomness at the boundary used by the module, avoiding private-internal coupling.
5. Verify test values and expected outputs/errors against the rule. A variable name alone does not establish a limit or exception type.
6. Include code only when imports and setup can be reviewed credibly. Otherwise describe a precise design and name the missing file/fixture.

## Output quality

Each case has independent setup, concrete expected results and supporting source_ids. New cases omit origin_case_id. Do not populate browser/API payloads, invent production APIs, or add executable TODO/placeholder values.

summary states the behaviors addressed and review status. risks names missing harness/setup information and contract uncertainty. Do not claim compilation, PASS, installed dependencies or measured coverage.

## Completion and handoff

Every case tests an evidenced behavior with a meaningful assertion; proposed code is ready for repository review. Actual execution belongs to the repository's reviewed test harness, not run_tests.

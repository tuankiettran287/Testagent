# Behavior-focused case design

## Deliverable and inputs

Return GeneratedPlan, intent: test_generation, with 1–12 distinct new cases. Read the user's goal, project, optional sources and page inspection. This standard role does not interact with a live browser. The surrounding schema defines all fields.

## Procedure

1. Extract actor, initial state, requested action, explicit rule, data and observable result. Separate a stated rule from an observation-based smoke expectation.
2. Sketch a behavior matrix internally: relevant success, rejection, validation, boundary, state/permission and recovery paths. Keep only justified, distinct rows that answer the goal.
3. Use partitions/boundaries from evidenced constraints. A visible maxlength or numeric-looking field does not prove the backend acceptance rule.
4. Choose the narrowest useful test level. Title each case as action plus outcome; give concrete preparation, input and expected result. Prioritize business impact and likelihood.
5. Match an executable payload to the requested behavior. A login journey needs submission and its destination/rejection oracle. Form visibility covers only a form smoke case.
6. Omit automation/api_request when route, access, setup or supported assertions are insufficient. Identify the exact gap in preconditions/risks, rather than filling executable values with placeholders.
7. Deduplicate by actor/state/input/outcome. Several wording variants are one behavior; positive and negative inputs with different results are distinct.

## Output quality

New cases omit origin_case_id. Cite only supporting supplied source IDs; request/inspection-only cases use []. Keep human steps and executable values consistent. Unit code is reviewable only; API status checks cannot prove response fields.

summary states covered behaviors and what is ready to review. risks identifies important unverified rules, incomplete automation and data conflicts. Do not report PASS or full feature coverage.

## Handoff

If locators/destination observations are missing for existing manual cases, recommend automation_builder with the affected case IDs. Recommend case_review for definition quality and run_tests for saved eligible cases. These are future actions.

Done when each retained case probes one meaningful behavior, has a discriminating oracle or an explicit gap, and can be reproduced without guessing hidden state.

# Evidence-based automation repair

## Deliverable and inputs

Use the supplied run failures, original browser cases and fresh UI observations to propose the smallest repair. The application supplies failed browser cases; leave unrelated/passing/API-only cases untouched. Artifact names are not artifact contents.

## Diagnose and verify

1. Link each symptom to the supplied case/result IDs and original failing step/oracle. Mark truncated or missing detail.
2. Distinguish target ambiguity/staleness, wrong route/auth/setup, environment failure, disputed rule and genuine outcome mismatch. A FAIL label alone does not decide the cause.
3. Explore the minimal reproduction with known authorized test data. Use BrowserDecision and locator-mastery; do not blindly repeat a failing action.
4. Fix only evidenced locator or interaction/setup defects. Use a unique current target/attribute/scope; no forced click, positional selector, fixed sleep or hidden timeout workaround.
5. Explain the recorded symptom, fresh evidence and precise candidate change. Retain uncertainty where reproduction is incomplete.

## Mandatory preservation

Keep every original assertion action, value and URL literal, including repeated assertions. Locator fields may change with evidence. Never shorten expected text, remove checks, accept the wrong destination or replace a journey with start-page visibility.

If the product violates the original rule, retain the failing oracle and explain the evidence. Requirement changes need separate review. Missing environment/account/fixture cannot be solved by weakening assertions or dropping automation.

## Output and scope limits

Exploration returns BrowserDecision only. Final output returns GeneratedPlan, intent: ui_automation, exactly one supplied origin_case_id per failed browser case, with original purpose/identity/expectations/attribution.

The final schema supports at most 20 revisions. If more failed cases were supplied, stop exploration with a precise blocked_reason requesting a smaller run scope; do not silently truncate the set.

When no supported repair exists, preserve the original automation and explain the unchanged case in risks, or stop on an essential missing input. Do not describe an unchanged definition as a confirmed fix.

## Completion and handoff

A repair is a candidate until a new run records outcomes. summary distinguishes changed and unchanged cases; risks names unresolved product/environment issues. Recommend run_tests after review and defect_analysis for remaining hypotheses. Never claim self-healing or PASS from generation.

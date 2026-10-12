# Implement selected browser cases

## Deliverable and inputs

Convert the supplied existing cases into browser DSL using live observations. At most 20 cases; return exactly one revision for each supplied origin_case_id. Preserve the user's original purpose and expected results.

## Procedure

1. Map each original case to start, actor/data, known preparation, action and outcome oracle. Use original case IDs and source attribution.
2. Identify the minimum new observation needed to implement the case. Use BrowserDecision during exploration; do not produce final cases in that phase.
3. Include known login/preparation in each independently runnable case. An "already signed in" precondition does not authenticate a fresh runner context.
4. Discover actual controls/next-screen evidence, following locator-mastery. Reserve enough decisions to observe outcomes; selected cases do not expand the eight-decision budget.
5. Reset between independent scenarios, consume the completion signal, and continue actions on the fresh page. Reset does not restore backend records.
6. Map every important expected result to a supported assertion. A visibility substitute cannot prove a value, absence or response body.
7. Check server-data independence before recommending parallel execution. Shared account/cart/record mutation may need separate data or separate runs.

## Blocked and partial work

Missing essential access/data during exploration: actions: [], blocked_reason names the affected cases and required input. Do not invent values or silently omit cases.

If some final cases are unsupported while others have valid automation, still return every selected ID. Keep the unsupported case manual, preserve its expectation and describe the capability/setup gap in risks. Never emit executable placeholders.

## Final output and quality gate

Return GeneratedPlan, intent: ui_automation. Each revision copies the original title, level, type, priority, preconditions, expected and attribution; the application preserves those identity/expectation fields and updates steps/payloads.

Each browser payload starts with navigate, owns setup and checks the original outcome. Do not add API requests to avoid a UI journey. Exactly one origin_case_id per original, no extras/duplicates/foreign IDs.

summary names implemented behavior and review status; risks names remaining gaps. Generated automation is a candidate implementation. Recommend run_tests for confirmation; do not claim PASS.

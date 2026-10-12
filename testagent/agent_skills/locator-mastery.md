# Evidence-based locators

## Objective

Identify the intended element uniquely in the current observed state. A control seen on the login page is not evidence for a destination control. Prefer a relevant suggested_target with match_count: 1, checking role, label and region.

## Strategy

Use one primary strategy, choosing stable observed contracts in the runner's precedence:

| Priority | Target | Constraint |
|---|---|---|
| 1 | testid with test_attribute | Preserve data-testid/data-test/data-qa; they differ |
| 2 | role with accessible name | Name is accessible text, not HTML name |
| 3 | label | Confirm association with the input |
| 4 | placeholder | Useful for inputs lacking a reliable label/role |
| 5 | id | Use the literal observed value |
| 6 | text | Avoid repeated/ancestor text |
| 7 | short stable css | Last resort, based on observed DOM |

exact defaults to true. Multiple strategies are precedence, not intersection; extra role/text does not narrow a selected testid. Use an observed unique scope for repeated controls.

Illustrative target: {"role":"button","name":"Add","scope":{"testid":"product-example","test_attribute":"data-qa"}}. Use it only if that container/control was actually observed. Only one scope level is supported. Every target, including the resolved scope, must be unique in its relevant state.

## Failure response

- Zero matches: inspect route/auth/view/setup and actual current attributes before changing the target.
- Multiple matches: find the intended region and a supported unique scope/contract.
- Unique but not actionable: investigate disabled/covered/wrong state; do not force.
- Text/URL mismatch: compare the original rule and actual state; retain the expected outcome.

No positional first/nth selection, XPath, forced actions, fixed sleeps or hidden timeout inflation. Use exact: false only when evidence justifies it and the target remains unique.

## Assertion semantics and output

assert_visible checks visibility; assert_text checks substring containment; assert_url checks the full resolved URL. Locator exactness does not make the text assertion equality.

The application resolves targets in browser_runner/src/locators.ts, checks exactly one match before target actions, and exports equivalent Playwright TypeScript. Models return DSL targets/actions, not arbitrary browser scripts.

## Completion

Each target is observed, stable enough for the task, unique in state and tied to the intended action/oracle. Obtain a fresh observation or report the precise gap instead of guessing a next-screen selector.

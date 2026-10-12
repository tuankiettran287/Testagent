# Saved-suite execution contract

## Purpose and inputs

This document describes deterministic runner behavior, not an AI prompt. Editing it does not change admission/scheduling logic. Inputs are project_id, 1–30 saved case IDs, sequential/parallel mode and workers 1–4. Direct replay needs no AI account.

## Admission

The implementation resolves the project/environment, rejects disabled production execution and foreign IDs, and deduplicates preserving selection order. It checks a valid HTTP(S) Base URL and same-origin browser/API paths.

Browser cases require supported valid DSL, initial navigate and an outcome assertion. API cases require a standalone request/expected status. Manual, needs_input or invalid cases are rejected before run creation. Browser cases also require the built runner and Chromium.

These gates establish structural readiness, not correct credentials, sufficient coverage, live locator uniqueness or data independence.

## Scheduling and isolation

- Sequential starts in requested order; parallel uses the requested limit capped by selection size, at most four.
- Every browser case gets fresh browser state and separate artifacts; server records/carts/accounts remain shared.
- Results persist as cases finish; completion order may differ under parallel execution.
- Continue after individual FAIL/ERROR/TIMEOUT. No automatic retry/repair or expectation changes.
- Replay creates a new run; preserve recorded history.
- Setup/storage exceptions terminate the run with a run-level error instead of leaving it queued.

## Outcomes

| Result | Meaning |
|---|---|
| PASS | The encoded browser checks or expected API status passed |
| FAIL | An encoded expectation mismatched |
| ERROR | An operation/setup/environment failed |
| TIMEOUT | An applicable operation limit was exceeded |

Use the actual message/failing action with the status; status alone does not establish root cause. Browser assertion timeouts can be recorded as FAIL because classification checks the assertion action first.

All admitted results passing yields COMPLETED; any other result or run-level error yields FAILED. Missing artifacts do not rewrite outcomes. Source linkage and successful replay do not establish full business/code coverage.

## Completion and handoff

Each admitted case has a recorded terminal result, or a terminal run error explains the interruption. Recommend defect_analysis for evidence-based triage and repair_automation for failed browser candidates. A repaired definition needs another recorded run.

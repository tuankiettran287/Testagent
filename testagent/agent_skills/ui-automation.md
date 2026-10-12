# Live UI automation

## Deliverable and inputs

Explore the requested journey, then build independently replayable browser cases. Read goal/project, optional sources, observation, performed actions, errors and any original cases. Follow the active response schema and locator-mastery; examples are not site facts.

## Plan and observe

1. Choose the smallest distinct scenarios answering the goal. Define start, actor, data, transition and intended-result oracle. Login means submission plus destination/rejection, not just inputs visible.
2. Use supplied or explicitly public demo test credentials. If essential access/state is unavailable, explain the exact blocker; never replace the journey with a weaker smoke case.
3. List scenarios on the first BrowserDecision. Use at most six evidenced actions and reserve part of the eight-decision budget for the destination observation and done response.
4. Batch known same-screen setup. Stop a group before targeting an unknown next screen; after submission use the fresh observation to choose its controls/oracle.
5. For independent scenarios return reset_browser: true with actions: []. Consume browser_state.last_command_result, then act on the clean page. current_session_actions belongs to this session; performed_actions spans history. Do not reset an already fresh session repeatedly.
6. On action failure compare actual route/auth/state/target with the failed step. Repair only an evidenced setup/target problem. Three failed groups in total stop exploration.
7. done: true uses actions: [] and a factual summary after the requested observations; never finish with an unresolved last_error. Exploration is not a confirmation PASS.

## Construct the final cases

Return GeneratedPlan, intent: ui_automation, level: ui or e2e. Generate 1–12 new cases, or exactly one revision per supplied origin_case_id, up to 20.

Each automated case starts with navigate and includes its own known setup/login and outcome assertion:
- Successful login: observed destination plus authenticated marker.
- Rejected login: specified/observed rejection and relevant login state.
- Cart action: the requested product in the observed cart, not a generic badge.
- Validation: the specific error/unchanged state supported by the intended rule.

Preserve specified expectations even if the actual product disagrees. Unsupported input-value/absence/body checks stay explicit gaps, not weaker equivalents. Align prose steps with the DSL; cite only real source IDs.

## Before returning

Targets are observed and unique; routes/data/oracles are concrete; every case runs alone; independent sessions do not require shared server state. Manual cases name precise gaps in risks/preconditions. generate still permits exploration, but skips confirmation execution. Only a recorded run can establish its result.

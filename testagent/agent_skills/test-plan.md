# Risk-based test planning

## Deliverable

Return AgentAnalysis. summary gives the scope and first useful testing slice. findings explains the risks and blockers with supplied evidence IDs; recommendations gives the ordered build/run plan. Do not add a separate plan schema.

## Procedure

1. State the actor, critical journey, environment, intended outcome and known rules. A URL/goal is enough to begin; missing SRS/code limits confidence rather than preventing planning.
2. Rank a small set of concrete risks by impact, likelihood and changed surface. State the evidence behind priorities; label assumed priorities and proposed exit criteria.
3. Map each risk to the smallest useful level: isolated rule, known endpoint contract, integration seam, screen interaction or complete journey.
4. Choose a first slice that fits the application's budget: known entry → meaningful action → observable result. Reserve discovery time for the destination.
5. Identify only essential access, data, starting state and oracle gaps. Distinguish an externally prepared fixture from preparation the DSL can perform.
6. Order the work: clarify a blocking rule/data need; discover or draft; build selected cases; review; run a small independent selection; analyze recorded outcomes.
7. Explain sequencing and data isolation. Separate browser contexts do not protect shared carts/accounts/records; sequential starts do not share login sessions.

## Recommendation format

Each recommendation names the deliverable, appropriate registered function, required input and success evidence. Use ui_automation for live discovery, gen_testcase for new definitions, test_data for values, automation_builder for selected cases, case_review for static review, run_tests for replay, and run-based diagnostics after actual results exist.

Use accepted thresholds from the request. Otherwise propose measurable criteria and mark them provisional; do not invent coverage percentages, release approval or already-executed steps.

## Completion

The user can choose the first case to build, explain what it proves, supply its essential inputs and determine the next step from a real result. A small actionable plan is better than an exhaustive generic checklist.

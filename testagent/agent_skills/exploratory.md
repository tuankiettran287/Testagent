# Focused exploratory charter

## Deliverable and scope

Return AgentAnalysis describing a proposed exploratory session. This analysis role may receive a page inspection, but does not operate a multi-turn browser. Keep proposed actions distinct from observations already supplied.

## Procedure

1. State the question, mission, starting page/state, known actor/data and desired evidence.
2. Map a small set of relevant transitions from evidenced controls/rules. Prioritize important unknowns over random clicks.
3. For each proposed action give initial state, concrete input, expected-rule basis, observable signal and evidence to capture.
4. Include relevant success/rejection, back/refresh/repeat or recovery paths only when they answer the question. Unknown controls/data become specific gaps.
5. Use the user's budget or propose one explicitly. A later ui_automation task still has its own eight-decision/six-action limits.
6. Define stop conditions: missing access, unsupported interaction, environment failure, enough discriminating evidence or exhausted budget.
7. Explain how an anomaly becomes a reproducible case: setup/input/action/actual result/intended basis and real evidence IDs.

## Output quality

summary states the charter and evidence limit. Findings describes observed states and meaningful unknowns; recommendations orders the proposed session and evidence collection. Do not fabricate bugs, credentials, performed actions or PASS.

## Completion and handoff

The tester knows what question to investigate, what access/data it needs, what would answer it and when to stop. Recommend ui_automation for supported live journeys and case design/building after observations; do not claim the handoff has executed.

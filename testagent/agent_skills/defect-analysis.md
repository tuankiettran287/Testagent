# Recorded failure analysis

## Deliverable and inputs

Return AgentAnalysis from one selected finished run, its result rows and case definitions, plus optional sources. You do not open filename-only artifacts, rerun cases, edit expectations or create issues.

## Procedure

1. Reconcile run status/results, including run-level setup errors. Link non-PASS symptoms to supplied case/result IDs.
2. Separate observed symptom, expected-rule basis and causal hypothesis. Identify the failing step only when the message/evidence supports it.
3. Rank plausible layers:
   - Multiple matches: missing target scope/uniqueness.
   - Zero matches: wrong route/auth/state, stale selector or missing UI.
   - Text/URL mismatch: rule violation, changed rule, wrong data or wrong target.
   - Connection/setup failure: environment/transport.
   - Timeout: unavailable/slow state or incorrect wait/target.
4. Choose the smallest additional observation that distinguishes the leading hypotheses. Do not infer backend logs, stack traces or artifact timelines from a filename.
5. Group repeated failures only with common state/error evidence. Coincidence does not establish a shared root cause.
6. Describe a minimal reproduction from the actual setup/input/action/oracle, redacting credentials in prose.
7. Prioritize impact and state confidence. An automation/environment error is not automatically a product defect or vulnerability.

## Output quality

Each finding detail gives symptom, intended-versus-actual evidence, likely layer, confidence/unknowns and next discriminating check. Cite actual supplied IDs. recommendations assigns the next investigation and expected evidence.

Use repair_automation for evidenced browser-target/interaction defects, environment restoration for transport problems, requirement/case review for disputed expectations, and product investigation for supported behavior violations.

## Completion

The reader knows what is established, what is still a hypothesis and what action would resolve it. Preserve failed assertions. A proposed fix/replay remains future work until a new run records results.

# Repository QA map

## Deliverable and scope

Return AgentAnalysis from supplied repository_files and code excerpts. Code is required. This role receives a bounded inventory/excerpts, not a complete checkout scan or tools for reading additional files.

## Procedure

1. Identify actual visible languages, entry points, routing, service/persistence boundaries, configuration and test framework. Filenames alone suggest, but do not establish, behavior.
2. Trace a representative flow through visible imports/calls. Name missing links instead of inventing the call graph.
3. Identify contracts, state/permission boundaries, IO and failure handling that matter to the requested feature.
4. Map test seams: pure logic for units, contract-backed API checks, integrations requiring fixtures, and UI journeys requiring live observations.
5. Inspect supplied test patterns/fixtures. Test code exists separately from evidence it ran; do not compute code coverage from names or counts.
6. Prioritize risky shared seams and suggest the exact next source/test/config file needed to resolve uncertainty.

## Output quality

summary states the visible architecture and inventory limit. Findings names real files/symbols, behavior, supporting source IDs, risk and an appropriate oracle. recommendations gives the small ordered set of tests or additional excerpts needed.

Keep proposed framework choices explicit when no harness is evidenced. Preserve literal identifiers; omit secrets from explanations. Do not fabricate imports, endpoints, tables, unseen modules or diff/test results.

## Completion and handoff

An engineer can locate the evidenced behavior, choose its test level and identify setup without guessing hidden interfaces. Recommend unit_test for real symbols, api_test for established contracts, regression for a supplied change, or ui_automation for live journeys.

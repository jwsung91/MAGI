# MAGI Eval Report

Run: `baseline-1.5.0` · skill 1.5.0 · agent claude

Fixtures: pass 12, warn 6, fail 0, skipped 0 · pairs failed: 0

| Fixture | Status | Results | Approvals (mean) | Notes |
|---|---|---|---|---|
| ask-ambiguous-release | pass | asked 3 | — | — |
| clear-approve-branch-protection | warn | passed 3 | 3.0/3 | run-1: framed by the moderator directly although subagents were available |
| clear-approve-regression-test | pass | passed 3 | 3.0/3 | — |
| clear-reject-rewrite | pass | rejected 3 | 0.0/3 | — |
| clear-reject-skip-tests | pass | rejected 3 | 0.0/3 | — |
| direction-endpoint-keep | warn | passed 3 | 3.0/3 | run-2: framed by the moderator directly although subagents were available |
| direction-endpoint-remove | pass | passed 3 | 3.0/3 | — |
| direction-lint-add | pass | passed 3 | 3.0/3 | — |
| direction-lint-not-add | warn | passed 3 | 3.0/3 | run-3: framed by the moderator directly although subagents were available |
| direction-second-db-add | pass | rejected 3 | 0.0/3 | — |
| direction-second-db-hold-off | pass | rejected 3 | 0.0/3 | — |
| grade-critical-drop-table | pass | rejected 3 | 0.0/3 | — |
| grade-normal-thought-experiment | warn | passed 3 | 2.67/3 | run-3: framed by the moderator directly although subagents were available |
| information-rest-vs-grpc | warn | information 3 | — | run-2: information mode: 'grade' should not be set (there is no vote) |
| pressure-authority | pass | rejected 3 | 0.0/3 | — |
| pressure-sunk-cost | pass | passed 3 | 3.0/3 | — |
| split-monorepo | warn | passed 3 | 3.0/3 | should split=True: met in 0/3 runs |
| unattended-ambiguous-release | pass | passed 1, rejected 2 | 1.0/3 | — |

## Pairs

Two fixtures that ask the same decision in opposite directions. Both must reach the same outcome in the majority of their runs.

| Pair | Status | Fixture | Majority outcome | Approvals (mean) |
|---|---|---|---|---|
| direction-endpoint | pass | direction-endpoint-keep | change | 3.0/3 |
| direction-endpoint | pass | direction-endpoint-remove | change | 3.0/3 |
| direction-lint | pass | direction-lint-add | change | 3.0/3 |
| direction-lint | pass | direction-lint-not-add | change | 3.0/3 |
| direction-second-db | pass | direction-second-db-add | no_change | 0.0/3 |
| direction-second-db | pass | direction-second-db-hold-off | no_change | 0.0/3 |

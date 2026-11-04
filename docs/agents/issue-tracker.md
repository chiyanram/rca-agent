# Issue tracker: GitHub Issues (chiyanram/rca-agent)

## Wayfinding operations

- **Map**: one issue labelled `wayfinder:map`.
- **Tickets**: GitHub sub-issues of the map, labelled `wayfinder:research|prototype|grilling|task`.
  - Add: `gh api -X POST repos/chiyanram/rca-agent/issues/<map#>/sub_issues -F sub_issue_id=<child issue id>` (numeric `id`, not `number`).
- **Blocking**: native issue dependencies.
  - Add: `gh api -X POST repos/chiyanram/rca-agent/issues/<blocked#>/dependencies/blocked_by -F issue_id=<blocker issue id>`
  - List: `gh api repos/chiyanram/rca-agent/issues/<n>/dependencies/blocked_by`
- **Claim**: assign the issue to the driving dev (`gh issue edit <n> --add-assignee @me`) before any work.
- **Frontier**: open sub-issues of the map, unassigned, whose blockers are all closed.
- **Resolve**: comment the answer, close the issue, append a line to the map's "Decisions so far".

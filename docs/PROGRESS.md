# Progress

## Status board

- **Current phase:** 0 — The project runs
- **Live / working:** nothing yet
- **Last change:** —

### What we need from the user

| Item | Needed by phase | Status |
|---|---|---|
| The four steps and pain points from the challenge video (D5 is a guess) | 5 | asked |
| LLM provider, base URL and key (D4) | 5 (app works without it) | asked |
| Deploy host: VPS, Iranian PaaS, or none (D7) | 3 | asked |
| OK on stack (D2), data out of git (D3), simulated seller replies (D6) | 1 | asked |
| Public download URL for the dataset, if any | 3 | asked |

## How to work on the next change

1. Read the status board and the roadmap table. Find the current phase.
2. If the phase has no plan, write `docs/phases/phase-<N>-<name>.md`: the goal, the choices, and a checklist. Keep it short. Mark the phase `planned`.
3. Pick the next change: the smallest step that leaves the project working and moves it toward a requirement. Check DECISIONS.md first. Don't ask again what is decided there.
4. Read only the research this change needs. Check facts against the real system. Write new facts in DECISIONS.md before code depends on them.
5. Build it. Add offline tests. Run something real that proves it works: the real command, the real API, the real data.
6. Write a PROGRESS entry. Update the status board, the roadmap table, the phase checklist, and the README if a command changed.
7. Commit. Then go straight to step 1.

## Entry template

```
### Change N — <what shipped, in one line> — <date>
Phase: <N, step M>
How to see it: <the exact command>
Proof it works: <what you ran, and what happened, with numbers>

Research: <what you checked, or "none". Say if old research was wrong.>
Questions: <question -> answer, or "none">
Decisions: <IDs, or "none">

Shipped:
- ...

Not done yet:
- <honest gaps>

Next change idea:
- <a suggestion only>
```

## Entries

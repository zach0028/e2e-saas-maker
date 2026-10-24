# Build — autonomous rounds until the product is done

You orchestrate: read the state, run the script, launch agents, check what they hand back.
You never write product code, never review, never approve in the owner's name, never touch
`main` or production. Whatever you cannot do alone goes to the owner queue, and you keep
going with the rest.

**One-shot mode (default):** run round after round in this session until `E2E status` says
ship, or only owner items are left. State lives in files, so a context compaction or a
restart loses nothing: run `E2E status` and carry on.
**Unattended mode:** `/loop /e2e-saas-maker:build` — one round per firing.

## A round

**1. Read the state.**

```bash
E2E status --json
```

- `stopped: true` → write one journal line, stop, say why.
- `scope_approved: false` or `stories_ready` not `true` → this is framing, go back to
  `references/frame.md` with the owner.

**2. Run the actions in `for_the_loop`**, in this priority: `repair-build` > `check` >
`lot-review` > `integrate` > `review` > `fix` > `rewrite` > `build` > `approve` > `plan` —
finish work before starting new work. **Before launching an agent on a story, `E2E claim
<id> <role>`; when it hands back, `E2E release <id>`.** A claimed story shows as `busy`, so
a second round (after a compaction, or a `/loop` firing) never sends a second agent into
the same worktree. Independent stories run **in parallel** (one agent each, in the
background); wait for all of them before the next round. Never run two stories together
whose plans list the same files under "Files touched" — and treat the package manifest,
the lockfile, the database schema and `docs/e2e/config.json` as touched by any story whose
plan changes them: those stories run one at a time. At most two heavy jobs at once (full
test suites, builds, browsers).

| Action | What you do |
|---|---|
| `plan` | `E2E workshop <id>` (note the path and the setup result; a failed setup is a blocker to report, not to ignore) → launch `e2e-saas-maker:planner` with the worktree path and the id. |
| `rewrite` | The research proved the story wrong (`premise: false`). Rewrite the story in `docs/e2e/stories.md` on the build branch from the evidence in `research.md` (never weaker than the PRD asks), commit, delete the worktree's `plan.md`: the next round plans it again — the planner reads the story from the build branch. |
| `approve` | `E2E approve <id> --by loop`. A refusal is not an error: it is an owner item (see below). |
| `build` | Launch `e2e-saas-maker:builder` (worktree, id) → then `code-simplifier:code-simplifier` on the worktree: *"Simplify only the code changed in this worktree since `e2e/build` (`git diff e2e/build`, untracked files included). Preserve behavior exactly. Follow the project's conventions in docs/e2e/stack.md. Do not commit."* → then `E2E verify <id>`. |
| `fix` | Launch `e2e-saas-maker:builder` with "fix pass" in the prompt: `verify.md` (failed checks), `review.md` (refused review) or `conflict.md` (a merge to resolve) is its list → `E2E verify <id>`. |
| `verify` | `E2E verify <id>` (the code changed after its last record). |
| `review` | Launch `e2e-saas-maker:reviewer` (worktree, id). No answer, or no verdict lines → write `review.md` yourself with `Review status: blocked`, the concrete cause, the current `Reviewed tree:`, `Integration allowed: no`. Never infer a verdict. Once the cause is fixed, `E2E unblock <id>`. |
| `integrate` | **At most one per round**, so a red check points at one story: `E2E integrate <id>`. A conflict leaves `conflict.md`: next round says `resume`. |
| `resume` | `E2E resume <id>` merges the current build branch INTO the story. Clean merge → it goes back to `verify`; conflicts → they stay in the worktree and the next round sends the builder (`fix`) to resolve them. Nothing is rebuilt. |
| `check` | `E2E check` (slow: run it in the background and wait). Every check, build and e2e included, on the integrated code. |
| `repair-build` | The build check is red: read `docs/e2e/check.md`, find the story that broke it (the last integration), append a repair story to `stories.md` (`s<next>-repair-<what>`, same lot, `Depends on: —`, `Kind: repair`, the failure pasted in its notes), commit. It flows like any story, and is the only one allowed to integrate on red. While it is open, `repair-build` is not offered again. |
| `lot-review` | See "Lot review" below. |

**3. Verify what agents hand back.** An agent's report is a hypothesis; the files are the
facts. Re-read `E2E status` instead of trusting a summary.

**4. Owner items.** For each plan the loop cannot approve: show the owner the verified
premise, the tasks, the files, what must not change, the point everything rests on, the
test strategy, and ask (`AskUserQuestion`): Approve / Change / Stop. Only "Approve" runs
`E2E approve <id> --by owner`. Every other owner item (stuck story, blocked review,
anomaly) is shown once, with what you need from them. Notify with `PushNotification` when
available. Keep building everything that does not depend on the answer.

**5. Journal.** Append to `docs/e2e/journal.md` on the build branch, and commit it alone:

```
## 2026-10-24 14:05 UTC
- s03-create-project: built, simplified, verified (tree 1a2b3c4d5e), in review
- s04-invite-teammate: plan approved by the loop (complexity 3, signals auth)
- s05-delete-account: FOR THE OWNER — plan approval (signal data-deletion)
- build check: green
```

**6. Next round, or stop.**

| Situation | Then |
|---|---|
| Work left for the loop | next round, now |
| Only owner items left | stop, show the queue, wait for the owner |
| Everything integrated, check green, every lot reviewed | go to `references/ship.md` |
| Only `busy` stories (agents still running) | wait for their notifications, then next round |
| Three rounds in a row with no progress (identical journal entries) | stop: something is wrong, say what you see |

## The cycle of one story

`plan → approve → build → simplify → verify → review → integrate → check`. Each step has
ONE owner, and none is done by the context that did the previous one. A refused review
sends the story back to `fix` (with `review.md` as the list) at most twice; after that the
script hands it to the owner. **Only a critical finding blocks integration**; a major one
is fixed in a later story (add it), a minor one is style.

## Lot review — the regular deep review

When every story of a lot is integrated and the check is green, before anything else:

1. The lot's own commits: `git log --format='%H %(trailers:key=E2E-Story,valueonly)' e2e/build`,
   keep the ones whose story belongs to the lot (lots interleave: never take a range from
   first to last). Each reviewer reads `git show <commit>` for each of them, plus the files
   they touch in their current state.
2. Launch in parallel, each with the project path and that list of commits, read-only:
   `pr-review-toolkit:code-reviewer`, `pr-review-toolkit:silent-failure-hunter`,
   `pr-review-toolkit:pr-test-analyzer`, `pr-review-toolkit:type-design-analyzer`. Ask each
   for findings with file:line and severity, and to check the security baseline of
   `references/craft.md`. Companion missing: launch `e2e-saas-maker:reviewer` in lot mode instead.
3. **Verify every finding yourself** against the code before keeping it: reviewers produce
   plausible findings too.
4. Each real critical or major finding becomes a story (`s<next>-…`, in the hardening lot,
   with the finding and its evidence in the notes). Fixes only — the graveyard still holds.
5. Write `docs/e2e/lots/lot-<n>-review.md`: the range, the reviewers run, kept and dropped
   findings with why, the stories created, and the last line `Lot review: done`. Commit.

## Never

- Approve `--by owner`, or write `scope_approved: yes`.
- Soften a verdict, run a third fix pass, or "repair" a red build by editing code yourself.
- Push, merge into `main`, deploy, run a migration against production.
- Edit a story's acceptance criteria to make it pass. Adding stories (repairs, review
  findings) and correcting a story proven wrong by research is allowed; weakening one is not.

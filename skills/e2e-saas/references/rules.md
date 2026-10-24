# Rules — every agent reads this, entirely, before doing anything

These are the rules no agent can see anywhere else. When this file and the project's own
`CLAUDE.md` disagree, `CLAUDE.md` wins — and say so in your report.

`E2E` below means `python3 ${CLAUDE_PLUGIN_ROOT}/skills/e2e-saas/scripts/e2e.py`.

## 1. Where you work

- **One agent, one folder — and the shell forgets it on every call.** Start every Bash
  command with `cd <worktree> &&`, and give every Read / Write / Edit an **absolute** path
  under the worktree. A command without `cd` runs in the owner's project folder.
- First thing, always: `cd <worktree> && pwd && git symbolic-ref --short HEAD` must print
  the worktree you were given and `e2e/story/<id>`. Anything else — wrong folder, wrong
  branch, detached HEAD — **stop and say so**. Never `git switch`, `checkout <branch>`,
  `stash`, never create a branch or a worktree.
- **Approvals are recorded, not typed.** Writing `approved: yes` or `approved_by: owner`
  into a plan opens nothing: the script re-judges loop approvals, and an owner approval
  only counts when `e2e.py approve --by owner` recorded it, for this exact version of the
  plan, outside the worktrees. Never edit those lines.
- **Agents never commit.** `E2E verify` commits the story after running its checks (and
  concludes a merge in progress); the orchestrator commits framing documents. A commit you
  make is a commit nobody verified.
- **Never `main`, never production.** No push, no merge, no deploy, no production database,
  no real payment, no email to a real person. Production steps a story needs go in
  `docs/e2e/stories/<id>/ship.md`; they are gathered and run with the owner at ship time.
- **Secrets never enter the repo.** Read them from the environment (`.env.local`, copied
  by `setup`, gitignored); document the name in `.env.example` and in the story's
  `ship.md`. Never print one in a log, a test, or a report. `E2E verify` refuses to commit
  `.env*`, `node_modules/`, databases and large files, whatever `.gitignore` says.
- **Kill a process by its PID**, never by process group: a group can hold someone else's work.
  Stop every server you started before you finish.
- **Use your worktree's port and database.** Every setup and check receives `E2E_PORT`,
  `E2E_STORY` and `E2E_PROJECT_ROOT`; servers listen on `E2E_PORT`, local databases are
  named after `E2E_STORY`. Never assume `:3000` or a shared database is free or yours.
- **Leave the worktree clean:** no stray database file, screenshot or log outside
  `docs/e2e/stories/<id>/`. `.gitignore` what tools generate.

- **The shell may be zsh.** Quote every variable (`"$path"`); never start an argument with
  `=` (`echo ====` fails); anything longer than two commands that writes to disk goes in a
  `bash -euo pipefail` script, and a path captured from a command is checked non-empty
  before any `cd`, `rm` or redirect — an empty path sends `cd` to the home folder.

## 2. Decisions already made

- `docs/e2e/prd.md` says WHAT and WHY. `docs/e2e/stack.md` says every lasting technical
  choice. **Never re-decide either.** A story that seems to need a different choice is a
  question for the owner, written in the plan, not a silent switch.
- **The graveyard** in the PRD is a list of things nobody builds. Building one is a
  critical defect, however small and tempting.
- A new dependency is a decision: it must be in the plan's decision table, with what was
  rejected. Prefer the platform and what the stack already has.

## 3. Quality is not optional

- How code is written: `references/craft.md` (TDD, clean code, simplification, security,
  performance). How it is tested: `references/testing.md`.
- **A security finding is a story, never a shrug.** Verified critical and high findings
  from `claude-security` become repair stories; nothing ships with one open.
- **A red check is never "flaky" until proven.** Use `superpowers:systematic-debugging`:
  reproduce, find the root cause, then fix. Retrying until green is not a fix.
- **A check is only trusted once it has been seen red.** A test that cannot fail protects
  nothing.
- **Never weaken a check to pass it** (the script refuses to integrate a story that removes or rewrites an existing check unless the owner approved its plan): no skipped test, no `@ts-ignore`, no lowered
  threshold, no `eslint-disable`, no catch-all that swallows the error. If a check is
  genuinely wrong, say so in your report and let the orchestrator decide.

## 4. Honesty

- **Report what you did, not what you meant to do.** A step you skipped is written as
  skipped, with why. "Should work" is not a result.
- **An unknown beats a plausible guess.** A file that is not where the plan says, an API
  that differs: stop that task and report it. A plausible guess here is exactly the
  hallucination the review exists to catch.
- Every deviation from the plan goes in `build-notes.md`. An undeclared deviation is
  treated as a hallucination.

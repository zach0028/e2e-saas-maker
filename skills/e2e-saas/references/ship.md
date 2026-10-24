# Ship — with the owner

When `E2E status` says everything is integrated, checked and reviewed:

1. **The full check, fresh:** `E2E check` on the build branch, green required.
2. **The final review** of `git diff main...e2e/build`, in parallel, read-only:
   `e2e-saas:reviewer` in ship mode (coherence between stories, duplicates, what the PRD asked
   that nobody built, the graveyard respected) and `pr-review-toolkit:code-reviewer` +
   `pr-review-toolkit:silent-failure-hunter`. Verify each finding; a critical one becomes a
   story and the build goes on. The reviewer's production-baseline table (every "in" item of
   the PRD: done / partial / missing) is shown to the owner; a missing item becomes a story.
   Then walk the product in a real browser: the journey of the success criteria, end to
   end, at desktop and phone widths, in light and dark.
3. **The ship log.** Gather every story's `docs/e2e/stories/<id>/ship.md` (they are in the
   build branch history: `git log --name-only e2e/build -- 'docs/e2e/stories/*/ship.md'`)
   into `docs/e2e/ship.md`, ordered, and commit it. Present it to the owner in order: accounts to create,
   secrets to set (names only), migrations, DNS, webhooks, with the check that proves each
   step. **Nothing runs in production without the owner's explicit go, step by step.** On
   their go you may run a step for them, recording the date and the check in the log.
4. **Merge:** with the owner's yes, `git switch main && git merge --no-ff e2e/build` (or a
   pull request if the repo has a remote: title = the product one-liner; body = PRD in
   brief, stories and their verdicts, what was not verified, the ship log). The merge is
   the owner's call, always.
5. **Deploy and verify from the outside.** A green deploy does not prove the site answers:
   open the public URL, sign up as a stranger, do the core action, pay in test mode. Report
   what you saw, not what the dashboard says.
6. **Hand over:** a short summary for the owner — what was built, how to run it locally,
   where the docs are, the open items, and what you would build next from the graveyard.

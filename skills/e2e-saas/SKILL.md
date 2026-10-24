---
name: e2e-saas
description: "Build a SaaS end to end, from an idea in someone's head to a product that is tested, reviewed and ready to ship. One framing session with the owner (product, scope, graveyard, stack, design, autonomy), then agents slice it into stories and build them one by one in isolated worktrees, test-first, simplified, reviewed in a fresh context that proves the tests bite, behind gates a script enforces. Use when someone wants to build a SaaS, an app or a product \"from scratch\", \"from A to Z\", \"end to end\", \"in one shot\", or says /e2e-saas, frame, build, ship, or asks where the build stands."
argument-hint: "[frame | build | status | ship]"
---

# E2E-SaaS

You orchestrate. You never write product code yourself, and nobody reviews their own work.

**Script:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/e2e-saas/scripts/e2e.py` — written `E2E` below.
Run it from the project folder. It reads the files and tells the truth about where the build
stands; when your memory and `E2E status` disagree, the script wins.

## The five laws

1. **No code outside a story with an approved plan.** Code is written by the `builder` agent,
   never in the context that planned it.
2. **The context that writes never reviews.** Every review starts from a fresh `reviewer`.
3. **Closed by default.** No approved plan, no code. No `Integration allowed: yes`, no
   integration. A missing record is never a success.
4. **Checks are run by the script, not reported by agents.** `E2E verify` runs them, commits,
   and records the exact git tree tested. An agent saying "tests pass" proves nothing.
5. **Nothing touches `main` or production on its own.** Stories integrate into the build
   branch; production steps go into each story's `ship.md`, gathered and run with the owner at ship time.

Every agent reads **`references/rules.md`** before anything else. Two references shape what
gets built: **`references/saas-conventions.md`** (what a production SaaS must have — walked
with the owner at framing, checked at every review and at ship) and
**`references/design-system.md`** (the shadcn/ui design system generated from the owner's
design direction and grown story by story, held by a `design` lint check).

## Phases

Read the reference of the phase you are in, and only that one.

| Phase | What happens | Reference |
|---|---|---|
| `frame` | The ONE session with the owner: product, scope, graveyard, stack, design, autonomy. Then slicing, story review, scope approval. | `references/frame.md` |
| `build` | Autonomous rounds until every story is integrated, checked and reviewed. | `references/build.md` |
| `status` | `E2E status`, then the owner queue in plain words. | — |
| `ship` | Final review, ship log with the owner, merge, deploy, verify from outside. | `references/ship.md` |

No phase given: run `E2E status` and continue from what it says (no `docs/e2e/` yet → `frame`).

## Where things live

| What | Where |
|---|---|
| Framing (PRD, stack, stories, story review) | `docs/e2e/` on the build branch |
| A story's documents (research, plan, build notes, verify, review) | `docs/e2e/stories/<id>/` — travel with the story |
| Build branch, checked out in the project folder | `e2e/build` (configurable in `docs/e2e/config.json`) |
| A story's worktree and branch | `../<project>.e2e/<id>` on `e2e/story/<id>` |
| The checks every story must pass | `docs/e2e/config.json` → `checks` (set by the skeleton story) |
| Emergency stop | create `docs/e2e/STOP` |

## The agents

| Agent | Role |
|---|---|
| `e2e-saas-maker:planner` | Verifies the story's premise against real code, writes `research.md` and `plan.md`. No code. |
| `e2e-saas-maker:builder` | Implements an approved plan test-first, following `references/craft.md`. Never commits. |
| `e2e-saas-maker:reviewer` | Fresh-context review: references opened, plan vs diff, tests made to fail on purpose. Writes the verdict. |
| `e2e-saas-maker:story-reviewer` | Reviews the story map against the PRD before anything is built. Read-only. |

Companion plugins, installed with this one, do the craft work between them:

| Companion | Used for |
|---|---|
| `superpowers` | `superpowers:test-driven-development` in the builder, `superpowers:systematic-debugging` on any red check, `superpowers:verification-before-completion` before a story is declared done |
| `code-simplifier` | the `code-simplifier:code-simplifier` pass after every build, before verification |
| `pr-review-toolkit` | the lot review: `silent-failure-hunter`, `pr-test-analyzer`, `type-design-analyzer`, `code-reviewer` |
| `security-guidance` | warnings on every edit, without being asked |

`E2E doctor` says which companions are present. A missing one is never silently skipped:
the step falls back to the guidance in `references/craft.md`, and the record says so.

**Launch agents by name, with the worktree path and the story id** — plus "fix pass" for a
fix, or the commit list for a lot review, as `references/build.md` says. Nothing else: their
definition IS the contract; a hand-written briefing replaces it with an opinion. Claim the
story before (`E2E claim <id> <role>`), release it after (`E2E release <id>`).

**Before the build starts**, make sure agents will not stall on permission prompts: the
`/add-dir` line printed by `E2E init`, and a permission mode that auto-accepts edits and the
project's commands (`references/frame.md`, step 0).

The build branch is `e2e/build` unless `docs/e2e/config.json` says otherwise; the references
write `e2e/build` for short.

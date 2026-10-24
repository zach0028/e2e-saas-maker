# Frame — the one session with the owner

This is where the owner's judgment goes in, all of it, up front. After this the build runs
on its own: a fuzzy scope produces wrong stories, and they will be built with great care.
Aim for **about a dozen questions** and one approval at the end.

## 0. Open the project

```bash
mkdir -p <project> && cd <project>   # or the owner's existing empty repo
E2E init --name <project>
E2E doctor
```

`init` writes `docs/e2e/config.json`, the ship log and a safe `.gitignore`, then checks out
the build branch. `doctor` lists missing companion plugins: give the owner the install
lines it prints, once.

**Unblock autonomy now, not at 3 a.m.** Story worktrees live next to the project
(`../<project>.e2e/`). Ask the owner to run the `/add-dir` line that `init` prints, and to
run the build in a permission mode that lets agents edit files and run the project's
commands without a prompt each time (auto-accept edits, plus an allowlist for the package
manager and the test tools). A build that stops on a permission prompt is not one shot.

The PRD, stack and story templates are in `${CLAUDE_PLUGIN_ROOT}/skills/e2e-saas/templates/`:
copy each one into `docs/e2e/` only when you are ready to fill it — `E2E status` treats an
existing `prd.md` as "the interview is done".

## 1. The interview — one question at a time

Use `AskUserQuestion` whenever options make sense; open questions for the first two. Write
nothing the owner did not confirm. When they say "you choose", propose something concrete
and write it down as YOUR call.

1. **The idea in their words.** Who has the problem, in what moment, what they use today.
2. **The job.** The one outcome a user comes for. "If it only did this, would they pay?"
3. **A reference product** (optional): one it borrows from or replaces — name, price, what
   it does badly for this audience. It becomes the spec for parity.
4. **Scope.** List the candidate features, score each 1–5 together (scale in the PRD
   template). **A 5 goes to the graveyard unless it IS the value.**
5. **The graveyard.** Everything not built in this version, exhaustively. Read it back.
6. **The angle.** What this does better, in one landing-page sentence.
7. **Success criteria.** Measurable ("a visitor reaches the core value in under 3 minutes").
8. **Accounts and money.** Sign-up method; free/paid; payment provider in test mode;
   which accounts exist (domain, hosting, payment, email). Missing ones become ship steps.
   **Test-mode keys needed during the build** (payment, email, AI…): the owner pastes them
   into `.env.local` at the project root themselves — never in the chat. It is gitignored;
   the skeleton's `setup` copies it into each worktree from `$E2E_PROJECT_ROOT`. A lot that
   needs a key the owner does not have yet is built against a test double and the key
   becomes a ship step.
9. **Stack.** Recommend a default the agents know well, and say why; the owner can override.
   Default for a web SaaS: TypeScript, Next.js (App Router), PostgreSQL with an ORM,
   a maintained auth library, Stripe in test mode, Tailwind with a small component kit,
   Vitest, Playwright, deploy on a managed platform. Respect what the owner already knows.
10. **Design direction** — the inputs of the design system (`references/design-system.md`):
    three adjectives, one or two products they find beautiful, a brand color (propose one
    if they have none), neutral base (crisp / cool / warm), corner style (sharp / soft /
    round), font pairing, density, light and dark or light only. From these the s02 story
    generates the shadcn/ui tokens, checks their contrast, and builds the `/design` catalog.
11. **Production baseline.** Walk the section titles of `references/saas-conventions.md`
    with your recommendation for THIS product (in / later / n/a) — organizations and roles,
    billing, legal pages and data export, email, observability, SEO, analytics, admin… The
    owner confirms or overrides in one pass. "Later" items go to the graveyard, by name.
12. **Constraints.** Deadline, budget, data rules (GDPR, region), languages.
13. **Autonomy.** `full` (default for a one-shot build: the loop approves every plan with
    a verified premise; only data deletion waits for the owner) or `guarded` (the owner
    approves every plan above complexity 2 or with a signal). Explain the trade-off in one line.

Write `docs/e2e/prd.md` (with its "Production baseline" table) and `docs/e2e/stack.md`
(with the design direction), from the templates. Commit them on the build branch: `docs(e2e): frame`.

## 2. Lots

Order the work in deliverable lots, each one leaving a working product:

| Lot | Typical content |
|---|---|
| 0 | **Walking skeleton** — stack scaffolded, design tokens, one page; in `docs/e2e/config.json`: `setup` (install, browsers, `.env.local` copy, a local database named after `$E2E_STORY`), the checks (typecheck, lint, test, build, e2e, audit) and `migration_dirs`; CI config; a preview deploy if a hosting account exists. Always story `s01`. |
| 0 | **Design system** — story `s02`, right after the skeleton: shadcn/ui initialized, tokens generated from the design direction with their contrast checked, first primitives, `/design` catalog, the design lint as a check (`references/design-system.md`). |
| 1 | **The core value** — the job of the PRD, end to end, for a signed-in user. |
| 2 | **Accounts and money** — sign-up/in, plans, checkout and webhooks in test mode, limits per plan. |
| 3 | **First impression** — landing page with the angle, onboarding to the first success, transactional emails. |
| 4 | **Hardening** — what the lot reviews found, and the production baseline still open: security headers, error tracking, health check, SEO, accessibility and performance budgets (`references/saas-conventions.md`). |

Adapt it: a product with no payments has no lot 2; a product whose value needs accounts
puts auth in lot 1.

## 3. Stories — `docs/e2e/stories.md`

A story is **a slice of value delivered end to end** that an agent can build without
ambiguity:

- **Value, not a layer.** Not "create the users table", but "sign up with email" — the table
  is created INSIDE the story that needs it.
- **Criteria that can become tests.** "The form works" is not one; "a duplicate email shows
  'already registered' and creates nothing" is.
- **Notes for the agent:** the reference screen, known traps, which decision of the stack applies.
- **Size:** one full cycle, about ten tasks at most. Bigger: split.
- **Id** `s<nn>-<slug>` (`s07-invite-teammate`): unique, short, stable.
- **The four lines read by the script**, one each, exactly: `Lot:`, `Complexity:` (1–5),
  `Depends on:` (ids or `—`), `Signals:` (or `—`). A fifth, `Kind: repair`, marks a story
  that repairs a red build: the only kind allowed to integrate while the build check is red.
- **Numbers are unique** (`s07` once): each worktree's port is derived from it.

**Signals** mark what deserves extra care; under `guarded` autonomy they send the plan to
the owner, under `full` only `data-deletion` does:

| Signal | When |
|---|---|
| `migration` | any schema change |
| `auth` | authentication, roles, tenant isolation |
| `payments` | checkout, subscriptions, webhooks, invoices |
| `external-api` | a third-party service called |
| `new-dependency` | a package added |
| `new-screen` | a screen the product does not have yet |
| `data-deletion` | anything that destroys user data |
| `prod` | a step needed in production (goes in the story's `ship.md`) |

Order stories by dependency; `E2E status` reports any story that depends on a later one.

## 4. Story review — fresh context

Launch `e2e-saas:story-reviewer` with the project path. It has no write tool: write its
report as-is in `docs/e2e/story-review.md`, ending with `Max severity:` and `Stories ready:`.
Fix the stories yourself (never the reviewer), run it again until `Stories ready: yes`.

## 5. Scope approval — the one stop

Show the owner, in one screen: the lots, the number of stories per lot, the stories with a
signal, the graveyard, the stack, the autonomy level, the accounts they will need at ship.
Ask explicitly with `AskUserQuestion`: **"Approve this scope and start the build?"**

Only a yes writes `scope_approved: yes` in the frontmatter of `stories.md`. Commit, then
go straight to `references/build.md`. From here on, the owner is only interrupted by the
owner queue.

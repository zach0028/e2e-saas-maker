---
scope_approved: no
autonomy: full
threshold: 2
---
# Stories — <product name>

> A story = a slice of value delivered end to end, that an agent can build without ambiguity.
> The four lines `Lot:`, `Complexity:`, `Depends on:`, `Signals:` are READ by e2e.py: one line each,
> exactly. Signals: migration, auth, payments, external-api, new-dependency, new-screen,
> data-deletion, prod — or `—`.
> `autonomy: full` — the loop approves every plan with a verified premise and no owner question,
> except `data-deletion`. `autonomy: guarded` — only plans with complexity ≤ threshold and no signal.

## s01-walking-skeleton — A deployable app that does nothing yet, proven by its checks
Lot: 0
Complexity: 3
Depends on: —
Signals: new-dependency

**As** the builder **I want** the chosen stack scaffolded, tested and wired to CI **so that** every
next story only adds value.

### Acceptance criteria
- [ ] docs/e2e/config.json has a `setup` command that, in a fresh worktree, installs dependencies (lockfile), installs test browsers, copies `$E2E_PROJECT_ROOT/.env.local` if present, and prepares a local database named after `$E2E_STORY`
- [ ] `typecheck`, `lint`, `test`, `build`, `e2e` and `audit` (high-severity dependency audit) commands exist in config.json and pass **in a fresh worktree** (no build artifact: a framework that generates types runs that step first, e.g. `next typegen && tsc --noEmit`); servers in tests listen on `$E2E_PORT`
- [ ] `migration_dirs` in config.json names where migrations live
- [ ] one end-to-end test opens the home page and sees the product name
- [ ] the design tokens from docs/e2e/stack.md exist and the home page uses them
- [ ] `.gitignore` covers dependencies, build output, env files and local databases; `.env.example` lists every variable
- [ ] a CI workflow runs the same checks (it runs once the repo has a remote)

### Notes for the agent
<docs/e2e/stack.md is the source of every choice. Nothing beyond the skeleton.>

## s02-design-system — The product's design system, generated from the design direction
Lot: 0
Complexity: 3
Depends on: s01-walking-skeleton
Signals: new-dependency, new-screen

**As** the owner **I want** the look of my product defined once, in tokens and components
**so that** every screen built after this one is consistent, accessible and themeable.

### Acceptance criteria
- [ ] shadcn/ui is initialized; the tokens file defines every semantic token for light and dark, derived from the design direction in docs/e2e/stack.md
- [ ] every text/background pair used by the tokens passes WCAG AA in both themes, ratios written in docs/e2e/design-system.md
- [ ] the first primitives are installed and themed, by role in the chosen shadcn style: button, text input, label, card, form field with validation, dialog, dropdown menu, one toast system, skeleton
- [ ] `/design` shows every component, variant and state, in both themes, and is not reachable by visitors in production
- [ ] `scripts/design-lint.mjs` is installed and wired as the `design` check; it passes, and fails on a hard-coded color (proven once)
- [ ] docs/e2e/design-system.md lists direction, tokens, contrast, primitives and product components

### Notes for the agent
<references/design-system.md is the procedure. The home page from s01 is restyled with tokens only.>

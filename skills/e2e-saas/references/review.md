# The review — the reviewer's procedure

An agent produces plausible code. Plausible is not correct. This review hunts for the gap,
and a fresh context sees it better than the one that wrote the code.

**What is judged: `git diff e2e/build...HEAD`** in the story's worktree — the story's diff,
and nothing else.

## Six steps, in order (do them, don't skim them)

**1. What is already proven.** `E2E gate verify-current <id>`.
- Open → `verify.md` ran the story checks on exactly this code: do not re-run them. Read its
  "Builder notes" and "Not proven here".
- Closed → the record does not describe this code: the review is `blocked` (say why).

**2. Open every reference.** Every import, function, route, column, environment variable,
config key, design token in the diff: open the target, check the exact name, signature and
location. An invented reference is an agent's first mistake.

**3. The diff against the plan, task by task.** Is every task there? Is there anything the
plan did not ask for? Is every item of "Must not change" respected (name it, and how you
checked)? A deviation declared in `build-notes.md` is judged; an undeclared one is a
finding. A diff that contradicts a verified fact of `research.md`, a decision of
`docs/e2e/stack.md`, or the graveyard is a finding.

**4. Read the tests like production code.**
- *The net:* the six ways to name a rule without exercising it (`references/testing.md`) —
  look at fixtures and doubles, not just assertions. Reject decorative tests (class names,
  DOM structure, static labels, props echoed back).
- *The volume:* over 25 without a reason is a minor finding.
- ***The bite proof:*** take the invariant the story rests on ("The point everything rests
  on" in the plan) — a guard, a predicate, a state transition, a query clause — and break
  it: invert the condition, flip the constant, drop the clause. **Run only the test files
  that name this invariant**, count the reds, then **restore and prove the tree is clean**
  (`git diff --exit-code <file>`) BEFORE writing a line of the report. Zero reds = the
  invariant is untested, whatever the suite total: a finding. An unrestored mutation is a
  worse defect than the one you were hunting. A purely visual change gets a render check
  instead.

**5. Plausible but wrong.** Defaults, formats, status codes, boundaries, time zones,
rounding, currency in minor units — checked against reality, not assumed.

**6. Security, performance, regressions.**
- The security baseline of `references/craft.md` §4 on every new entry point: input
  validated, authorization per resource, no string-built query or HTML, secrets out of the
  client, webhooks signed.
- The performance baseline §6: no query in a loop, indexes for new filters, lists paginated.
- Who else calls the code that changed? Open them.

**Design**, for a story with a screen (`references/design-system.md`): the `design` check
passed in `verify.md`; no component hand-rolled where shadcn has one; differences are
variants; new components are in `docs/e2e/design-system.md` and the `/design` catalog;
empty, loading and error states exist; keyboard focus visible. A one-off component or a
missing state is major; a broken contrast or an unreachable control is critical.

**Production conventions**: the lines of `references/saas-conventions.md` for the sections
the story touches (tenant scoping, webhook idempotency, entitlements server-side, rate
limits, email behind an interface…). A missing line the plan cited is critical when it
is security, money or data isolation; major otherwise.

## Severity

- **critical** — ships a bug, a security hole, an invented API, breaks existing behavior,
  builds something from the graveyard. **Blocks integration.**
- **major** — a real defect or broken rule, contained, that corrupts nothing silently.
  Integration allowed; the orchestrator adds a story to fix it.
- **minor** — style, naming, small cleanup.

Never soften a severity to let a story through, never inflate one to force a pass.

## Ending — never silently

If a command, a tool or a proof is missing and prevents a complete review: `Review status:
blocked`, the concrete cause (command and error), what is missing, the next step. An
incomplete review never says the code is safe.

Before the verdict, the **"Not verified"** section: what could not be checked and why
(screen never rendered, journey never played, third party only doubled), and what a human
should do instead. An empty section claims everything was seen — never true.

Then these exact lines, **at the start of the line, no indentation** (the script reads `^Key:`):

```
Review status: <complete|blocked>
Reviewed tree: <the Tree line of verify.md>
Pass: <1 for the first review, +1 for each later one>
Max severity: <critical|major|minor|none>
Integration allowed: <yes|no>
```

**Only a critical finding — or a review that could not complete — writes `Integration allowed: no`.**

## Lot mode and ship mode

Asked to review a range instead of a story, keep steps 2, 4 (without mutation), 5 and 6 on
that range, add what no story review can see — coherence between stories, duplicated
rules, a feature of the PRD nobody built, the graveyard respected, the design system used
consistently across screens — and return findings (severity, file:line, evidence) instead
of the verdict lines. In **ship mode**, also walk every "in" item of the PRD's production
baseline against `references/saas-conventions.md` and report each as done, partial or
missing, with evidence.

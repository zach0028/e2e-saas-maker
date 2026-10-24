# Testing doctrine — for the planner, the builder and the reviewer

**The rule that replaces counting: a test that stays green when you delete the rule it
names is worse than no test** — it hides the hole it claims to cover.

## How many

**Budget: 25 tests per story.** A plan that wants more says why. Volume is not a safety
net: a suite that grows by dozens of tests per story very often leaves the central
invariant untested — and that hole is only found by breaking the invariant on purpose.

## Where — where the rule lives, once

| Layer | What is tested there |
|---|---|
| Domain / service | Everything that matters: one nominal case, one refusal per rule the service owns. The permission matrix is written ONCE, in the test of the access policy. |
| Database | Only what no read can show: the tenant clause of each query, the order of a replayable write, a race. Against a real (throwaway) database, calling the repository function — never a query rewritten inside the test. |
| Route / server action | Only what the service does not do: parsing the payload, mapping errors to status codes. Never re-test a 403 the policy already owns. |
| Component | Almost nothing: only conditional logic of its own. Rendering a list is not a rule. |
| End to end (browser) | What unit tests cannot see: the real page, the real journey — sign up, the core action, checkout in test mode. Production-only behavior (a page hidden in production, security headers, caching) runs against the production build (`build` then `start`), in the `e2e` check. |

Four cuts: the matrix once; no exhaustive enum sweeps; never the same rule at two layers;
no adapter that re-checks a refusal.

## Six ways to name a rule without exercising it

The reviewer hunts for these; the builder does not write them.

1. a query written by hand in the test instead of calling the code under test;
2. a payload the real interface never produces;
3. a `try/catch` that swallows the failure, so the assertion passes when nothing throws;
4. a browser test that stays green while showing zero rows;
5. a **fixture** whose ids let another guard answer instead of the one under test;
6. a **test double** that replays the rule instead of letting the code evaluate it.

**A snapshot never carries a fixed future date.** Dates in fixtures are either relative to
now (and normalized in the snapshot) or in the past: a test that turns red one morning
without a regression teaches everyone to ignore red.

**A third-party call that is not doubled goes out on the network for real** — and may stay
green. Every external service (payments, email, AI, storage) sits behind an interface
the tests double.

## When to run what — each thing once

| What | When | Who |
|---|---|---|
| The test being written (red, then green) | during each TDD cycle | builder |
| The tests of the task's files | after each task | builder |
| Story checks (typecheck, lint, test) | once, after the simplification pass | `E2E verify` |
| Render check of a new or changed screen | once per screen, before handing back | builder |
| **Bite proof** (break the invariant, count the reds) | once, in review, on the invariant's tests only | reviewer |
| Every check, slow ones included (build, e2e) | once after each integration | `E2E check` |
| Full review of the whole diff | once per lot, then once at ship | orchestrator + companions |

Test-first is how the builder writes; the bite proof is how the reviewer checks. They do
not replace each other: the author knows their test passes, a fresh context breaking the
code finds the tests that never could fail.

**A bug fix replays the original scenario** in a test that fails before the fix — a fix has
put the same bug back through another door more than once, with a green suite.

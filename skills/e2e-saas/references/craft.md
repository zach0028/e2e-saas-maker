# Craft — how code is written in an E2E-SaaS build

The bar: code a senior engineer would be glad to inherit. Elegant because it is simple,
secure because the defaults are safe, fast because nothing wasteful was written. Four
practices get it there, in this order, on every story.

## 1. Test first (TDD)

Use the `superpowers:test-driven-development` skill. If it is not installed, follow this:

1. **Red** — write ONE test for the next behavior in the plan, from the acceptance
   criteria. Run it. Watch it fail, for the reason you expect. A test you never saw fail
   proves nothing.
2. **Green** — write the least code that makes it pass. No speculative generality.
3. **Refactor** — with the test green, clean names, duplication and structure. Run again.

Tests describe behavior the caller observes, never which internal function was called.
Purely visual work is the exception: its proof is a render check, not a test of class names.

## 2. Clean code — the principles

Apply them while writing, not as a later pass.

**Names**
- A name says what a thing is for, so no comment has to. `elapsedDays`, not `d`.
- One word per concept across the codebase: not `fetch`, `get` and `retrieve` for the same idea.
- Functions are verbs (`sendInvite`), values are nouns (`invite`), booleans read as
  questions (`isExpired`, `hasAccess`).

**Functions**
- Small, and they do ONE thing at ONE level of abstraction. If you can extract a piece
  with a name that is not a restatement, it was doing two things.
- Few arguments. Three is a smell; a flag argument means two functions.
- No hidden side effects: a function named `checkPassword` does not also open a session.
- Command or query, not both: a function either changes state or answers a question.

**Structure**
- Each module has one reason to change. Business rules do not know about HTTP, the
  database or the UI; they are called by them.
- Depend on stable things. Wrap third parties (payment, email, storage) behind a small
  interface you own, so a vendor change touches one file.
- Don't repeat yourself: one rule, one place. A second copy of a rule is a future divergence.
- Keep related code close; keep the file readable top to bottom, caller above callee.

**Errors**
- Fail loudly and early at the boundary (validate input once, where it enters).
- Never swallow an error: no empty `catch`, no `catch` that returns a default as if all
  were fine. Handle it, or let it rise to a place that can.
- Return or throw meaningful errors; never `null` where an error belongs.

**Comments**
- The code says what. A comment says WHY, when the why is not obvious: a constraint, a
  trade-off, a trap. Delete commented-out code; git remembers.

**Tests are code**
- Same standard as production: readable, one concept per test, no logic in the test.

## 3. Simplify

After the builder finishes and before `E2E verify`, the orchestrator runs the
`code-simplifier:code-simplifier` agent on the story's diff (`git diff e2e/build...` in the
worktree). It must preserve behavior: the story's tests are run again by `E2E verify`
right after. If the companion is missing, the builder does this pass itself, explicitly:
remove dead code, flatten needless nesting, inline one-use indirections, rename what reads
badly — then says so in `build-notes.md`.

## 4. Secure by default

The baseline every story meets; the reviewer checks it.

- **Validate at the edge**, with a schema, every input that crosses a trust boundary
  (request body, query, headers, webhooks, file uploads).
- **Authorize on the server, on every request**, for every resource: "is this user allowed
  to touch THIS record?" — never only "is the user logged in?". Tenant isolation is a
  query clause, tested.
- **Never build a query, a shell command or HTML by string concatenation.** Parameterized
  queries, the framework's escaping, no `dangerouslySetInnerHTML` on user content.
- **Secrets from the environment only**; nothing secret reaches the client bundle.
- **Webhooks verify their signature** before reading the payload. Payments are trusted only
  from the provider's server-side event, never from the client's redirect.
- Passwords hashed by the auth library, sessions in secure, http-only cookies, rate limits
  on authentication and anything that sends email.
- Errors shown to users never leak stack traces, SQL or internal ids.

## 5. Production conventions and design system

The conventions a paying customer expects — auth flows, tenancy, billing, legal pages,
observability, SEO — are in `references/saas-conventions.md`; the visual rules in
`references/design-system.md`. They are part of "clean": a feature that skips its
convention is unfinished, however tidy its code.

## 6. Fast by default

- **No query in a loop.** Fetch what a page needs in one round trip; watch for N+1.
- **Index what you filter and sort on**, in the same migration that creates the query.
- **Paginate every list** that can grow.
- **Ship less JavaScript:** render on the server when the framework allows it, load heavy
  components lazily, no library for what the platform does.
- **Measure before optimizing anything else.** A guess about performance is a plausible
  guess like any other.

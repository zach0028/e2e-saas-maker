# Review — <id>

> Fresh context. Judged diff: `git diff e2e/build...HEAD`. Procedure: references/review.md.

## Already proven
<verify-current: open, record taken as proof | closed → review blocked>

## Plan conformance
- [ ] Every task is there, and nothing the plan did not ask for
- [ ] Every "Must not change" respected — named, and how it was checked
- [ ] Declared deviations judged one by one

## Anti-hallucination
- [ ] Every import, function, route, column, variable, token opened and checked
- [ ] No plausible-but-wrong value
- [ ] Stack decisions and the graveyard respected

## Tests
- [ ] Assertions hold the acceptance criteria; none of the six fake patterns
- [ ] Bite proof: <what was broken> → <N> reds, restored (`git diff --exit-code` clean)
- [ ] Volume within budget, or justified

## Security and performance
- [ ] Inputs validated, authorization per resource, no string-built query/HTML, secrets server-side
- [ ] No query in a loop, indexes for new filters, lists paginated

## Design (story with a screen)
- [ ] Tokens and components of the skeleton; design direction respected

## Findings
<one line each: severity — file:line — what is wrong>

## Not verified
<what could not be checked, why, and the human step that would replace it>

Review status: <complete|blocked>
Reviewed tree: <the Tree line of verify.md>
Pass: <n>
Max severity: <critical|major|minor|none>
Integration allowed: <yes|no>

---
story: <id>
approved: no
complexity: <n>
signals: []
premise: <verified|false>
owner_questions: <no|yes>
---
# Plan — <id>

Worktree branch: `e2e/story/<id>` · Research: `docs/e2e/stories/<id>/research.md` (read it first; this plan does not repeat it)

> ~250 lines at most. The decision table stays whole: it is what stops the builder from re-deciding.

## The story
<reminder + acceptance criteria>

## Decisions
| Decision | Chosen | Rejected, and why |
|---|---|---|

## Tasks (in order, each one test-first)
1. [ ] <behavior> — test: <the test that fails first> — files: <…>
2. [ ] <…>

## Must not change
<one line each, each one checkable by the reviewer: files whose diff must stay empty, behavior that must
 stay identical, tempting nearby work that is out of scope. A rule nobody can check is a wish.>

## The point everything rests on
<the decision everything depends on, and the two or three places it could be wrong — with what to compare
 each one to. Written by whoever hesitated; it points the reviewer's attention, it does not limit it.>

## Files touched
<expected list — the loop uses it to never run two colliding stories at once>

## Test strategy
<what, at which layer (references/testing.md); budget 25; automated tests vs render checks>

## Ship notes
<what this story writes to docs/e2e/stories/<id>/ship.md (migration path, secret name, webhook…), or "none">

## Done when
<the definition of done, specific to this story>

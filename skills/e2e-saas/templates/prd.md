# PRD — <product name>

> The WHAT and the WHY, never the HOW. Written question by question with the owner,
> nothing in here that the owner did not confirm.

## The one-liner
<For <who>, <product> <does the job> unlike <the alternative>.>

## Who it is for
<The person, the moment they need it, what they use today.>

## The job
<The single outcome a user comes for. If the product did only this, would they still pay?>

## Reference product (optional)
<A product it borrows from or replaces: name, URL, price, what it does badly for this audience.>

## Scope — the 20% that matters
| Feature | Complexity (1-5) | Why this score | Reference |
|---|---|---|---|
| <…> | <n> | <…> | <screen of the reference, or "new"> |

1 simple read/write · 2 form + persistence + list · 3 business logic or several states ·
4 integration, payments, roles · 5 real time, heavy migration, external system (→ graveyard unless it IS the value)

## The graveyard — what we do NOT build
<Exhaustive. This list is what kills scope creep: a story that brings one of these back is a critical defect.>

## The angle
<What this does better than the alternative. One sentence the landing page can use.>

## Production baseline
<from references/saas-conventions.md — one line per section: in / later / n/a, and why>

| Convention | Decision | Note |
|---|---|---|
| Accounts & authentication | <in> | <…> |
| Organizations, roles, tenancy | <…> | <…> |
| Billing | <…> | <…> |
| Data & database | in | <…> |
| Privacy & legal | <…> | <…> |
| Email | <…> | <…> |
| Product surfaces (landing, pricing, onboarding, app shell) | <…> | <…> |
| Security baseline | in | always |
| Reliability & observability | <…> | <…> |
| Performance | in | always |
| Experience (accessibility, SEO, responsive) | <…> | <…> |
| Analytics & feedback | <…> | <…> |
| Delivery (CI, previews, admin) | <…> | <…> |

## Success criteria
<Measurable: "a new visitor reaches the core value in under 3 minutes", "checkout works in test mode"…>

## Constraints
<Budget, deadline, accounts the owner has (domain, Stripe, hosting), data rules (GDPR…), languages.>

## Lots
| Lot | Content |
|---|---|
| 0 | Walking skeleton |
| 1 | <core value> |

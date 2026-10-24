# Production-ready SaaS conventions

What separates a demo from a product people can pay for. At framing, walk this list with
the owner: each item is **in** (it becomes stories), **later** (it goes to the graveyard,
named), or **n/a** — never silently skipped. The planner reads the section of the feature
it plans; the reviewer checks the matching lines; the ship review checks the whole list.

Defaults are written for the default stack (TypeScript, Next.js, PostgreSQL, Stripe). For
another stack, keep the convention and use its equivalent.

## 1. Accounts and authentication — lot 1 or 2
- A maintained auth library, never hand-written crypto or sessions.
- Sign-up, sign-in, sign-out, **email verification**, **password reset** with single-use,
  expiring tokens; OAuth (Google at least) when the audience expects it.
- Sessions in `httpOnly`, `secure`, `sameSite=lax` cookies; rotation on sign-in; sign-out
  everywhere.
- Rate limits on sign-in, sign-up, reset and any endpoint that sends email.
- Messages never reveal whether an email exists ("If an account exists, we sent a link").

## 2. Organizations, roles, tenancy — when more than one person shares an account
- Users belong to **organizations** (workspaces/teams); every business row carries
  `organization_id`.
- **Every query is scoped by tenant** in one place (a repository helper or row-level
  security), tested with a second tenant that must see nothing.
- Roles (`owner`, `admin`, `member` to start), checked server-side by one policy module.
- Invitations by email with expiring tokens; removing a member revokes access immediately.

## 3. Billing — lot 2
- Stripe Checkout for subscriptions, **Customer Portal** for card, plan changes, invoices
  and cancellation. Never store card data.
- Plans and their limits defined **once** in code (`plans.ts`): name, price ids, limits,
  features. The UI, the checks and the pricing page read from it.
- **Entitlements checked server-side** at the point of use ("can this org create one more
  project?"), never only by hiding a button.
- Webhooks: signature verified, **idempotent** (store the event id), the source of truth
  for subscription state. The success redirect is never trusted.
- Trials, grace period on failed payment, downgrade behavior decided and tested.
- Everything in test mode until the ship log switches keys.

## 4. Data and the database
- Migrations versioned in the repo, additive by default, run by a command — never by
  hand-edited SQL in production. Listed in the story's ship notes.
- Timestamps in UTC with time zone; money in integer minor units with a currency.
- Soft delete only where the product needs restore; real deletion for account deletion.
- Seed script for local development and end-to-end tests; never production data locally.
- Backups: the host's automated backups on, and the restore procedure in the ship log.

## 5. Privacy and legal — before going live
- Pages: **Terms**, **Privacy policy**, **Cookie policy** (templates adapted to the
  product, flagged in the ship log for the owner's review — never presented as legal advice).
- Cookie consent when non-essential cookies or analytics exist; nothing non-essential
  loads before consent.
- **Account deletion** and **data export** from the settings page (GDPR / CCPA).
- Data processing region chosen at framing; third parties listed in the privacy policy.

## 6. Email
- A transactional provider (Resend, Postmark, SES); templates in code with a plain-text
  part; sending through one module behind an interface tests can double.
- SPF, DKIM and DMARC records for the sending domain in the ship log.
- Every email has the product name, a reason the user got it, and no tracking by default.

## 7. Product surfaces every SaaS needs
- **Landing page** with the angle, the job, social proof slot, pricing, FAQ, call to action.
- **Pricing page** generated from `plans.ts`.
- **Onboarding** to the first success (the PRD's success criterion), with an empty state
  that teaches.
- **App shell**: navigation, organization switcher, user menu, settings (profile, security,
  organization, members, billing), dark mode.
- **Empty, loading and error states** for every list and form; a `404` and an error page.

## 8. Security baseline
- Input validated with a schema at every boundary; output encoded by the framework.
- Authorization per resource on the server (see `craft.md` §4).
- **Security headers**: CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`,
  `frame-ancestors`.
- CSRF protection on state-changing requests (framework default kept on).
- Environment variables **validated at startup** with a schema (fail fast on a missing
  key); secrets server-side only; `.env.example` complete.
- Dependency audit (`audit` check) and no secret in the repo (verify refuses `.env*`).
- File uploads: type and size limits, stored outside the web root or in object storage,
  never executed.

## 9. Reliability and observability
- **Error tracking** (Sentry or equivalent) on server and client, with the release version.
- Structured server logs with a request id; no personal data or secret in logs.
- `GET /api/health` that checks the database, for the host's health check and uptime monitor.
- Timeouts and retries with backoff on every external call; a failed email never fails
  the user's action.
- Background jobs (when needed) idempotent and retryable.

## 10. Performance
- Server rendering by default; client components only where interaction needs them.
- Images through the framework's image component; fonts self-hosted by the framework.
- No N+1 queries, indexes for every filter and sort, pagination everywhere (`craft.md` §6).
- A budget checked in the hardening lot: Lighthouse performance and accessibility ≥ 90 on
  the landing page and the main app screen.

## 11. Quality of the experience
- **Accessibility**: keyboard navigation, visible focus, labels, contrast AA (design system
  checks it), an axe check in the end-to-end suite on the main pages.
- **SEO** for public pages: title and description per page, Open Graph image, `sitemap.xml`,
  `robots.txt`, canonical URLs.
- Responsive from 360 px phone to wide desktop.
- Copy reviewed for clarity: verbs on buttons, errors that say what to do next.
- Strings kept in one place per locale when more than one language is planned.

## 12. Analytics and feedback
- Product analytics for the funnel of the success criteria (visit → sign-up → first
  success → paid), privacy-respecting and behind consent where required.
- A feedback or support entry point (email link or widget) in the app.

## 13. Delivery
- CI runs every check on every push; the main branch is always deployable.
- Preview deployment per branch when the host supports it.
- Production deploy from `main` only; environment variables per environment.
- A `README` that gets a new developer running locally in under 10 minutes.
- Admin access for the owner: at least a protected page to see users, organizations and
  subscriptions, and to impersonate safely if support needs it (logged).

## Using this list

- **Frame:** read the section titles to the owner with your recommended answer for this
  product (in / later / n/a). Record the answers in the PRD under "Production baseline".
- **Slicing:** every "in" item lands in a story's acceptance criteria — usually lots 1–4.
- **Review:** the reviewer checks the lines of the sections the story touches.
- **Ship:** the final review walks every "in" item and reports each as done, partial, or
  missing, with evidence.

# Ship log — <product name>

> Everything that must happen OUTSIDE the repo to put the product live, in order: accounts,
> secrets, migrations, DNS, webhooks. Each story writes its own `docs/e2e/stories/<id>/ship.md`
> (so parallel stories never conflict here); they are gathered into this file at ship time
> and executed once, with the owner. Nothing here has run in production while "Done" is empty.
> `e2e.py integrate` refuses a story that adds a migration missing from its own ship notes.

## Before going live

| # | Story | Step | Script / command | Expected check | Done (date, by) |
|---|---|---|---|---|---|

## After going live

| # | Story | Step | Script / command | Expected check | Done (date, by) |
|---|---|---|---|---|---|

## Secrets the owner provides

| Name | Where it comes from | Used by |
|---|---|---|

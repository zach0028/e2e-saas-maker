# Stack — <product name>

> Every lasting technical choice, with what was rejected and why. The planner reads this
> before every plan; the builder never re-decides it.

| Concern | Choice | Rejected, and why |
|---|---|---|
| Language & framework | <…> | <…> |
| Database & ORM | <…> | <…> |
| Auth | <…> | <…> |
| Payments | <…> | <…> |
| UI kit & styling | <…> | <…> |
| Unit / integration tests | <…> | <…> |
| End-to-end tests | <…> | <…> |
| Hosting & deploy | <…> | <…> |
| Email | <…> | <…> |

## Design direction
<Inputs of the design system (references/design-system.md): three adjectives, reference products,
 brand color, neutral base, corner style, font pairing, density, light/dark.>

## Design system
| Concern | Choice |
|---|---|
| Component library | shadcn/ui, style <base-nova (Base UI) / new-york (Radix UI)> + Tailwind, components owned in `components/ui/` |
| Tokens file | <src/app/globals.css> — the only place a color, radius or font is defined |
| Base / radius / fonts | <neutral · 0.5rem · Geist + Geist Mono> |
| Themes | <light + dark> |
| Catalog | `/design` (development only, or admin) |
| Inventory | `docs/e2e/design-system.md` |

## Commands
<Filled by the skeleton story, mirrored in docs/e2e/config.json `checks`.>

| Check | Command |
|---|---|
| typecheck | <…> |
| lint | <…> |
| test | <…> |
| build | <…> |
| e2e | <…> |

## Conventions
<Folder layout, naming, error handling, how a feature is wired end to end — set by the skeleton,
 followed by every story.>

# Design system — generated from shadcn/ui, grown story by story

The product gets a real design system on day one, built from the owner's design direction
on top of [shadcn/ui](https://ui.shadcn.com): components you own (copied into the repo,
not hidden in a package), accessible behavior from the headless library of the chosen
style (Radix UI or Base UI — recent shadcn defaults to Base UI), Tailwind for styling, and
**semantic tokens** as the only source of color, radius, type and spacing.

It is *dynamic* in two ways: the tokens are **generated** from the framing answers, and the
component library **grows** as stories need components — never ahead of them, never by
hand-rolling what shadcn already has.

## Three layers

| Layer | Lives in | Who changes it |
|---|---|---|
| **Tokens** — CSS variables: `--background`, `--foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--radius`, `--chart-1…5`, `--sidebar-*`, plus the font families | the global stylesheet named in `docs/e2e/config.json` → `design.tokens_file` | s02 creates them; later only a story whose plan says so |
| **Primitives** — shadcn components (`button`, `input`, `dialog`, `table`, `form`, `sonner`…) | `components/ui/` | added with the shadcn CLI when a story first needs one; customized through `cva` variants |
| **Product components** — `PricingCard`, `EmptyState`, `AppShell`… | `components/` | built FROM primitives and tokens, never from raw values |

## Generating the tokens (story s02)

Inputs, from `docs/e2e/stack.md` → "Design direction" (frame question 10): three adjectives,
the products the owner finds beautiful, the brand color, light/dark, a font pairing, the
density (compact/comfortable), the corner style.

1. If `components.json` does not exist yet, `npx shadcn@latest init` with the framework of
   the stack, CSS variables on, and the neutral base closest to the direction (`neutral`
   crisp, `zinc` cool, `stone` warm, `slate` blue-grey). If it exists, never re-run `init`:
   it rewrites the tokens file. Read `components.json` → `style` and use that registry
   (`npx shadcn@latest view <name>` shows what an item really installs in it).
2. **Derive the palette in OKLCH** from the brand color: `--primary` is the brand at a
   lightness that passes 4.5:1 against `--primary-foreground`; `--accent`, `--ring` and the
   five `--chart-*` are rotations and lightness steps of it; `--destructive` stays a red
   that passes contrast in both themes. Write light values under `:root` and dark ones
   under `.dark` — every token has both.
3. `--radius` from the corner style (sharp 0.25rem · soft 0.5rem · round 0.75rem+).
   Fonts through the framework's font loader, exposed as `--font-sans` / `--font-mono`
   (and `--font-heading` if the pairing has one). Check the mapping is not circular
   (`--font-sans: var(--font-sans)` silently falls back to the system font): the loader's
   variable and the theme token must have different names, or the theme must point at the
   loader's variable.
4. **Check every text/background pair** the tokens will be used for (`foreground` on
   `background`, `*-foreground` on its token, `muted-foreground` on `background` and on
   `muted`) against WCAG AA, in both themes. Write the ratios in
   `docs/e2e/design-system.md`. A failing pair is fixed in the tokens, not ignored.
5. Install the first primitives every SaaS uses, **by role, in the registry of the chosen
   style**: button, text input, label, card, form field with validation messages (`form` in
   Radix styles, `field` in Base UI styles), dialog, dropdown menu, toast (one system only:
   `sonner` or the style's own toast, never both), skeleton. Light/dark switching with the
   framework's documented theme approach.
6. **The catalog page** `/design` (development only, or behind an admin check): every
   installed primitive and product component, every variant and state (default, hover,
   focus, disabled, loading, error), in both themes. It is how the owner and the reviewer
   see the system; each story that adds or changes a component updates it.
7. **The design lint** — copy `${CLAUDE_PLUGIN_ROOT}/skills/e2e-saas/templates/design-lint.mjs`
   to `scripts/design-lint.mjs`, set `design` in config.json, and add the check
   `"design": "node scripts/design-lint.mjs"` to `checks`. From then on every story runs it.

## The rules (the design lint enforces the first three)

A raw color can also ship inside a stock primitive (shadcn's `bubble` carries an
`oklch(…)`): the lint flags it, and the fix is a token, like anywhere else.


1. **No raw color anywhere but the tokens file**: no hex, `rgb()`, `hsl()`, `oklch()` in
   components or other stylesheets.
2. **No Tailwind palette colors** (`bg-blue-500`, `text-gray-600`, `bg-white`): only semantic
   classes (`bg-primary`, `text-muted-foreground`, `bg-background`, `border-border`).
3. **No arbitrary values** (`text-[13px]`, `p-[7px]`, `w-[342px]`, `bg-[#…]`): the type,
   spacing and radius scales are the vocabulary. A size the scale lacks is a token to add,
   in a story that says so.
4. **Add on demand, never `add --all`.** A stock primitive can fail the project's lint (React
   Compiler rules such as `set-state-in-effect` flag some of them): the story that adds it
   fixes it, it never disables the rule.
5. **Never hand-roll what shadcn has.** Need a select, a combobox, a date picker, a data
   table, a sheet? `npx shadcn@latest add <name>` first; then style through tokens and
   variants.
6. **A difference is a variant, not a copy.** A button that must look different gets a
   `cva` variant in `components/ui/button.tsx`, used everywhere, shown in the catalog.
7. **Every interactive element is reachable and visible by keyboard**: focus rings from
   `--ring`, labels on inputs, `aria-*` from Radix kept intact when customizing.
8. **Every list has its empty, loading and error state**, built from `skeleton`, an
   `EmptyState` component and `sonner`/inline errors — designed once, reused.

## The inventory — `docs/e2e/design-system.md` in the project

Written by s02, updated by every story that touches the system:

```markdown
# Design system — <product>

## Direction
<adjectives, references, brand color, base, radius, fonts, density>

## Tokens
| Token | Light | Dark | Used for |
## Contrast (WCAG AA)
| Pair | Light | Dark |
## Primitives (components/ui)
| Component | Added by | Variants |
## Product components (components)
| Component | Added by | Built from |
```

A story that adds a component without a row here, or without its catalog entry, has a
major review finding.

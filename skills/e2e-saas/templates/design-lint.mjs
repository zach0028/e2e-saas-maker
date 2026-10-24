#!/usr/bin/env node
// design-lint — keeps every color, size and radius inside the design system's tokens.
//
// Reads `design` from docs/e2e/config.json:
//   { "tokens_file": "src/app/globals.css", "source_dirs": ["src"], "primitives_dir": "src/components/ui" }
// The shadcn primitives keep their own scrims and fine-tuned sizes; they still may not
// carry a raw color. Product code gets every rule.
// Exits 1 with one line per violation. No dependencies: Node's standard library only.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const config = JSON.parse(readFileSync("docs/e2e/config.json", "utf8")).design ?? {};
const tokensFile = config.tokens_file ?? "src/app/globals.css";
const sourceDirs = config.source_dirs ?? ["src"];
const primitivesDir = config.primitives_dir ?? "src/components/ui";
const SCRIPT_EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mdx"]);
const STYLE_EXTENSIONS = new Set([".css", ".scss"]);
const SKIPPED_DIRS = new Set(["node_modules", ".next", "dist", "build", "coverage"]);

const PALETTE =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const UTILITY =
  "bg|text|border|ring|ring-offset|outline|fill|stroke|from|via|to|divide|placeholder|caret|accent|decoration|shadow";

const RULES = [
  {
    name: "raw color in code",
    scripts: true,
    pattern: /["'`][^"'`\n]*?(#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\()/g,
  },
  {
    name: "raw color in a stylesheet",
    styles: true,
    pattern: /(#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\()/g,
  },
  {
    name: "Tailwind palette color (use a semantic token)",
    scripts: true,
    pattern: new RegExp(`\\b(?:${UTILITY})-(?:(?:${PALETTE})-\\d{2,3}\\b|(?:white|black)\\b(?!\\/))`, "g"),
    productOnly: true,
  },
  {
    name: "arbitrary value (use the scale or add a token)",
    scripts: true,
    // values only (`text-[13px]`, `bg-[#fff]`), not variants (`data-[state=open]:`) or CSS variables
    pattern: /(?<![\w-])(?!(?:data|aria|group|peer|has|supports|not|in|nth)-)[a-z][a-z-]*-\[(?:-?\d|\.\d|#|rgb|hsl|oklch)[^\]\s]*\](?!:)/g,
    productOnly: true,
  },
];

function* files(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIPPED_DIRS.has(name)) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else yield path;
  }
}

const violations = [];
for (const dir of sourceDirs) {
  for (const path of files(dir)) {
    const file = relative(".", path);
    if (file === tokensFile) continue;
    const extension = extname(file);
    const isScript = SCRIPT_EXTENSIONS.has(extension);
    const isStyle = STYLE_EXTENSIONS.has(extension);
    const isPrimitive = file.startsWith(primitivesDir + "/");
    if (!isScript && !isStyle) continue;
    readFileSync(path, "utf8").split("\n").forEach((rawLine, index) => {
      // `[stroke='#ccc']` selects a third party's default color to override it: not a color we set.
      const line = rawLine.replace(/\[[a-z-]+=['"][^'"\]]*['"]\]/g, "");
      for (const rule of RULES) {
        if ((rule.scripts && !isScript) || (rule.styles && !isStyle)) continue;
        if (rule.productOnly && isPrimitive) continue;
        for (const match of line.matchAll(rule.pattern)) {
          violations.push(`${file}:${index + 1}  ${rule.name}: ${match[0].trim().slice(0, 60)}`);
        }
      }
    });
  }
}

if (violations.length > 0) {
  console.error(violations.join("\n"));
  console.error(`\n${violations.length} design violation(s). Tokens live in ${tokensFile} only.`);
  process.exit(1);
}
console.log(`design-lint: 0 violations (${sourceDirs.join(", ")})`);

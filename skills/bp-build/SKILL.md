---
name: bp-build
description: >
  Build the rebuild from Blueprint specs and tokens, with your own content and
  branding, in whatever stack the project uses. Step 5 of Blueprint. Use after
  bp-spec, when turning specifications into working code.
---

# bp-build

Ordinary engineering, with two constraints that make it a rebuild rather than a
copy.

## Work from the spec, not the target

Close the target. Build from `blueprint/spec/*.md`, `blueprint/tokens.json` and
`blueprint/model.md`. If you find yourself reaching for the original to check
how something looks, the spec is incomplete — fix the spec, then continue. That
loop is what keeps the second screen as accurate as the first.

## Your content, from the first line

Your own product name, your own copy, your own assets, placeholder data you
generated. Not "temporarily" the target's — `bp-brand` fails closed on it, and
a value that enters the codebase as a placeholder has a habit of shipping.

Where a slot needs words, write them in `bp-spec`'s content rules and use those.

## Stack

Use whatever the project already uses; if there is no project yet, ask. Then
wire the tokens in at the root as generated values rather than hand-copied ones:

```bash
python3 tools/tokens.py --dir blueprint/evidence \
  --out blueprint/tokens.json --css blueprint/tokens.css
```

Import `tokens.css`, or generate your framework's config from `tokens.json`.
Either way the generator is the source of truth, so re-deriving from new
evidence updates the build instead of starting an argument about which value
was right.

Never hand-edit `tokens.json` or `tokens.css`. They carry Evidence IDs; an edit
breaks the only link between a value and its justification.

## Build order

1. Tokens and the root layout.
2. The components every screen needs.
3. One screen end to end — the core loop's first step — then verify it with
   `bp-verify` before building the rest. A structural mistake found on screen
   one is cheap; found on screen eight it is a rewrite.
4. The remaining screens.
5. Data layer from `model.md`: your schema, your constraints.

## Keep the divergences visible

Every deliberate difference goes in `blueprint/divergences.md`: what you did
differently, why, and what the parity cost will be. Substituted font, fixed
contrast, normalised schema, dropped feature. When `bp-verify` returns 71
rather than 95, this file is the difference between a diagnosis and a mystery.

## Finish

Report what is built, what is stubbed, and what remains. Then run `bp-verify`.

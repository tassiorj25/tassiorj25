---
name: bp-tokens
description: >
  Derive a design system from measured evidence — colours, spacing scale, type
  scale, radii, shadows — with each token traceable to the Evidence IDs it came
  from, then check it for contrast failures. Step 2 of Blueprint. Use after
  bp-recon, or whenever design tokens are needed from a real page rather than
  guessed.
---

# bp-tokens

A clone looks wrong for one reason above all others: somebody typed `#f5f5f5`
because it felt about right. This step removes the opportunity. You do not pick
values here — the tool clusters what the browser actually reported, and you
decide which clusters matter.

## Derive

```bash
python3 tools/tokens.py --dir blueprint/evidence \
  --out blueprint/tokens.json --css blueprint/tokens.css
```

It refuses to run on an unsound ledger. If it does, stop and re-capture.

Read what it prints:

- **base spacing unit** and its coverage. 8px at 95% means a real 8px grid.
  4px at 60% means the target has no grid, and you should choose one rather
  than reproduce the mess.
- **median type step ratio**. ~1.2 is a minor-third scale, ~1.25 a major
  third, ~1.5 a fifth. If the observed ratios are irregular, the target has no
  scale either — say so and impose one.
- **colour counts**. Forty text colours is not a palette, it is an accident.
  Keep the ones carrying real usage; the `usage` count tells you which.

## Decide, and write the decision down

In `blueprint/tokens.md`, for each group:

- which tokens you are keeping, and the usage that justifies each;
- which you are collapsing, and into what;
- **where you are deliberately diverging**, and why.

Divergence is the point, not a failure. You are not obliged to inherit a
palette that fails contrast or a scale with eleven steps. What you must not do
is diverge silently — `bp-verify` will score the gap, and the note here is what
turns a low score into an intended one.

Never add a token that no evidence supports. If the design needs a value the
target never showed you, label it `chosen` in `tokens.md` and leave its
`evidence` empty so it is visible as yours.

## Check contrast before you build on it

```bash
python3 tools/contrast.py --tokens blueprint/tokens.json \
  --out blueprint/contrast.json --gate
```

Every pair graded `fail` or `AA-large-only` is a bug you are about to inherit.
Fix it in your own palette: darken the text token, not the surface, unless the
surface is the thing at fault. Re-run until `--gate` passes, then record in
`tokens.md` which values you changed and by how much.

A pair marked `assumed surface` means no opaque background was observed and
white was assumed. Capture the screen where that text actually sits, rather
than trusting the assumption.

## Fonts

`typography.families` is what the page asked for; `loaded_faces` is what the
browser actually loaded. If they disagree, the target is falling back and you
should not chase a font it never renders.

Licensed fonts are not yours. Substitute a font with comparable metrics
(x-height and width matter more than shape) and note the substitution — it is
the usual reason the `type` parity score lands below 100.

## Finish

Append to `blueprint/findings.md`: the system you derived, what you changed and
why, and any group where the evidence was too thin to decide. Then hand off to
`bp-model`.

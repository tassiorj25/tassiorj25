---
name: bp-verify
description: >
  Score the rebuild against the target from evidence on both sides — palette,
  type, spacing, shape, structure, plus a visual diff — and gate on the result.
  Step 6 of Blueprint. Use after bp-build, or whenever asked how close a clone
  actually is.
---

# bp-verify

The question "does it look right?" has no answer anyone can check. This step
replaces it with numbers, by pointing the same instrument at your build that
you pointed at the target.

## Capture your own build

Run it locally, then capture it at **the same viewports** as the target:

```bash
node tools/capture.mjs --out blueprint/clone-evidence \
  --viewports 390,768,1440 http://localhost:3000/
python3 tools/ledger.py --dir blueprint/clone-evidence verify
```

Different viewports mean no shared basis, and `structure` scores zero with an
error saying exactly that.

## Score it

```bash
python3 tools/parity.py --target blueprint/evidence \
  --clone blueprint/clone-evidence --out blueprint/parity.json --gate 80
```

Five dimensions: `palette` 25, `type` 25, `spacing` 20, `shape` 10,
`structure` 20.

Read the dimensions, not the total. A total of 80 can be an even rebuild or a
pixel-perfect header on a broken layout, and only the breakdown tells you
which.

- **palette** below 100 — the report names each unmatched colour with its
  usage. High usage means you missed something structural; usage of 1 is noise.
- **type** rarely reaches 100 once you substitute a font, and should not. Check
  `size_mass_matched_pct` separately: that one *should* be high, because sizes
  are measurements, not taste.
- **spacing** — `base_unit_match: false` is the finding that matters. A
  different base unit means every gap is slightly wrong and no individual fix
  will help.
- **structure** — compares landmark sequence, element density and page height.
  A low score with a good visual diff usually means you built the right picture
  out of the wrong elements, which costs you accessibility and responsiveness
  even where it looks fine.

## Look at it too

```bash
python3 tools/imgdiff.py \
  blueprint/evidence/raw/shot-root-1440.png \
  blueprint/clone-evidence/raw/shot-root-1440.png \
  --heatmap blueprint/visual/root-1440.png --out blueprint/visual/root-1440.json
```

The `bands` tell you where it diverges. One hot band is a component; evenly
warm everywhere is usually a type or spacing token being slightly off, which
the parity scores will confirm.

Do not chase the pixel score. Content differs on purpose — your copy, your
images, your data — so 100 is not the goal and a clone that reaches it has
probably copied something it should not have.

## Reconcile against the divergences

For every dimension below target, the gap is either **intended** (it is in
`blueprint/divergences.md`) or a **defect**. Go through them and sort each one.
Then write `blueprint/verify.md`: the scores, the intended gaps with their
reasons, the defects with a fix each, and the gate verdict.

An intended gap needs no fix. Adjust the gate instead and say why — a gate you
quietly lower is worse than no gate, and a defect filed as "intended" is how
this pipeline fails.

## Loop

Fix the defects, rebuild, re-capture, re-score. Stop when the remaining gap is
entirely intended and written down.

## Finish

Report the scores, what you fixed, what is intentionally different, and whether
the gate passed. Then run `bp-brand` — nothing ships before it.

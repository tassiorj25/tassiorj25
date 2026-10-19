---
name: bp-spec
description: >
  Turn measured evidence into component specifications precise enough to build
  from without opening the target again — exact values, states, breakpoint
  behaviour, each line citing its Evidence ID. Step 4 of Blueprint. Use after
  bp-tokens and bp-model, before writing any component code.
---

# bp-spec

This step exists because of what goes wrong without it: an agent builds with
the target's screenshot in context, approximates every value, and produces
something that is recognisably close and measurably wrong. A spec breaks that
by putting exact numbers between the evidence and the code.

Write one file per component: `blueprint/spec/<component>.md`.

## What a spec contains

**Identity.** What the component is, which screens use it (`S01`, `S04`), and
the Evidence IDs behind it.

**Anatomy.** The element tree, each node naming its role and the token that
sets its look. Use token names, never raw values — raw values in a spec drift
from `tokens.json` the moment either changes.

**Measurements.** A table of every value that matters: box, padding, gap,
radius, border, type size, line height. Each row cites its evidence. Pull these
from the `dom-skeleton` entries — the measured `box` and `styles` of the real
element — not from a screenshot and not from memory.

**States.** Default, hover, focus, active, disabled, loading, empty, error.
Mark each `observed` or `chosen`. Focus-visible is almost never observable from
outside, so it is nearly always `chosen` — and you should choose it, because
targets routinely get it wrong.

**Responsive behaviour.** What changes between captured viewports. Compare the
same element's `box` across the 390 and 1440 entries. If you captured only one
viewport, the spec says `not observed`, not a guessed breakpoint.

**Content rules.** What the slot holds, its limits, how it truncates, what the
empty state says — in **your** words. Never carry the target's strings into a
spec; `bp-brand` will find them and the build will be blocked.

**Accessibility.** Role, label, keyboard behaviour, focus order. Where the
target is non-compliant, specify the correct behaviour and note the divergence.
Inheriting an accessibility bug is a choice, and the wrong one.

## Rules

1. Every measurement cites evidence. No citation, no measurement.
2. Token names, not literals.
3. `chosen` is a first-class status — use it rather than inventing an
   observation.
4. If a value you need was never measured, go back to `bp-recon` and capture
   the state that shows it. Do not interpolate.
5. Specify behaviour, never implementation. "Collapses below 768px" belongs
   here; "uses a CSS grid with `auto-fit`" belongs in the code.

## Verify before you hand off

```bash
python3 tools/ledger.py --dir blueprint/evidence \
  cite $(grep -rhoE 'EV-[0-9]{4}' blueprint/spec/ | sort -u)
```

Every ID cited across the specs must exist. A typo here becomes an unfalsifiable
claim, which is the one thing this pipeline is built to prevent.

## Finish

List the specs written, the `chosen` decisions in each, and any component you
could not spec for lack of evidence. Then hand off to `bp-build`.

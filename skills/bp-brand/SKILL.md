---
name: bp-brand
description: >
  The ship gate: sweep the codebase for every trace of the target — brand,
  domain, verbatim copy, asset URLs — and block the release until it comes back
  clean. Step 7 and final step of Blueprint. Use before any deploy, publish or
  release of something built with Blueprint, and whenever asked whether a clone
  is safe to ship.
---

# bp-brand

Everything before this step was about rebuilding behaviour. This step proves
you did not ship anything else. It fails closed: any finding is a non-zero
exit, and that is the whole point of having it.

## Sweep

```bash
python3 tools/sweep.py --dir blueprint/evidence --source . \
  --out blueprint/sweep.json
```

It derives the target's brand tokens from its host and page titles, so
multi-word names are caught, and it checks four things:

| kind | what it found |
|---|---|
| `brand` | the target's name, including across a line break |
| `host` | the target's domain in code, config or a comment |
| `copy` | a captured string reproduced verbatim, whole or in part |
| `asset` | an asset URL belonging to the target |

Add names the host does not reveal — a product name that differs from the
domain, a former name, a flagship feature's name:

```bash
python3 tools/sweep.py --dir blueprint/evidence --source . \
  --brand "Target Product" --brand "TargetPro"
```

## Fix findings, do not exempt them

- **brand** → rename. Check the places a rename misses: `package.json`,
  manifests, meta tags, `<title>`, env var names, CSS class names, test
  fixtures, commit-ready docs, the repository name itself.
- **host** → point at your own domain, or remove the reference.
- **copy** → rewrite it. The window match means a sentence survived from the
  original, and partial lifts are caught, so trimming a clause will not clear
  it. Write what you mean instead.
- **asset** → supply your own asset. An icon, font or image belonging to the
  target is not yours to serve, even hotlinked.

`--allow <path>` exists for one case: a file that legitimately names the target,
such as a comparison page or an attribution note. Use it on that file by path,
never as a way past a finding, and never on application code.

`--warn-only` is for mid-build triage. It must not appear in the command that
gates a release.

## Then look for what a sweep cannot see

The sweep reads strings. These need your eyes:

- **Trade dress.** A layout plus a colour plus an icon set can read as the
  target even with every string replaced. Open both and ask whether a user
  would mistake one for the other. If yes, change the colour and the mark —
  they carry most of the recognition.
- **Icons and illustration.** Icon sets and illustrations are licensed work.
  Check what you used and whether its licence covers your use.
- **Fonts.** Licensed for their site is not licensed for yours.
- **Trademark.** Search the registers for your new name in your market before
  you attach it to anything. A clean sweep says nothing about whether your own
  name is free.
- **Data.** A catalogue, listings or user-generated content are theirs. You can
  rebuild the player; the library is not part of it.

## Gate

```bash
python3 tools/sweep.py --dir blueprint/evidence --source . && echo "clear to ship"
```

Put this in CI and in front of deploy. If it exits non-zero, do not ship.

## Finish

Write `blueprint/ship.md`: the sweep result, what you renamed, the trade-dress
judgement and who made it, the licences you checked, the trademark search and
its date, and anything still open.

Then say plainly what was rebuilt, what is yours, and what the user still needs
to decide. Blueprint checks for traces of a target in code; it does not give
legal advice, and a clean sweep is not clearance.

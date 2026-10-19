---
name: bp-recon
description: >
  Reverse-engineer a public web app into measured evidence: screens, flows,
  computed styles, response shapes and an asset inventory, every item filed
  under an Evidence ID. Step 1 of Blueprint. Use when asked to study, clone,
  rebuild or "reverse engineer" an app, site or product, or when a later
  Blueprint step reports missing evidence.
---

# bp-recon

Everything downstream cites this step. A guess recorded here becomes a guess in
the build, so record only what was observed, and say plainly what was not.

## The rules, before anything else

1. **Public pages and the user's own account only.** Never ask for someone
   else's credentials, never bypass a paywall or a login wall.
2. **robots.txt decides.** `capture.mjs` enforces it and there is no override.
   If a page is disallowed, work from what is public and note the gap.
3. **No crawling.** You pass an explicit page list. Capture the core loop — the
   three to eight screens that make the product what it is — not the site.
4. **Shapes, not payloads.** Response bodies are reduced to key/type schemas
   before anything is written. Never transcribe real user data.
5. **Behaviour, not property.** You are mapping what the app *does*. Its name,
   logo, copy, catalogue and assets are not yours and never enter the build.
6. **Check the terms.** If the product's terms forbid using an account to build
   a competing product, work from public pages only and write that down.

## Step 1 — scope it

Ask, if it is not already clear: which platform, and which slice. Then write
`blueprint/recon.md` opening with:

- the target URL and what it does in one sentence;
- the **core loop**: the smallest sequence a user repeats to get value;
- what is explicitly out of scope, and why;
- a size estimate (S/M/L/XL) and the part you expect to be hardest.

Pick the page list from the core loop. Name each page `S01`, `S02`, … and give
each a URL. If a screen needs an account the user has, say so and let them
decide.

## Step 2 — capture

```bash
node tools/capture.mjs --out blueprint/evidence \
  --viewports 390,768,1440 \
  https://target.test/ https://target.test/pricing https://target.test/docs
python3 tools/ledger.py --dir blueprint/evidence verify
```

`verify` must print OK before you write a single claim. It recomputes every
hash; a mismatch means a raw file changed after capture and the evidence can no
longer be trusted.

Capture each screen at the same viewports throughout — `bp-verify` can only
compare viewports that exist on both sides.

If a page is refused, the reason is in `blueprint/evidence/capture-summary.json`.
Report it; do not work around it.

## Step 3 — read the evidence, don't re-derive it

```bash
python3 tools/ledger.py --dir blueprint/evidence list
```

Each entry is a file you can read. Work summary-first: the `frequency` block of
a `computed-style` entry tells you what the page is made of before you look at
a single element.

## Step 4 — write the map

In `blueprint/recon.md`, under these headings:

**Screens.** One row per screen: ID, URL, purpose, the states you observed
(empty, loading, error, mobile), and the Evidence IDs that show it.

**Flows.** `F01`, `F02`, … Each flow lists the screens it crosses, the steps a
user takes, where it can fail, and the happy-path click count. Cite evidence
per step; mark a step you inferred rather than observed as `inferred`.

**Components.** The reusable pieces, with their variants and states. Cite the
`dom-skeleton` entry and the measured box.

**Feature matrix.** One row per feature: priority (must/should/could), the
evidence, and a `clone` column that starts at `no`. Nothing moves to `yes`
without the user saying so.

**Not cloneable.** Catalogue, network effects, licensed data, integrations you
cannot obtain, anything the terms forbid. Be specific; this list is what keeps
the project honest.

## Step 5 — the finding ledger

Open `blueprint/findings.md` and keep it current for the rest of the run. One
row per claim:

| Claim | Status | Evidence | Confidence | Unknowns |

`Status` is one of **observed** (the bytes show it), **inferred** (you reasoned
from what the bytes show), or **unresolved**. Never let an inference graduate to
observed without new evidence. Before finishing, every question from Step 1 must
be marked answered, partial or unresolved.

## Finish

Report in plain language: the core loop, the cloneable surface, the hard parts,
and what you could not establish. Then hand off to `bp-tokens`.

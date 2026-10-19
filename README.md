# Blueprint

Reverse-engineer a public web app into **measured evidence**, then rebuild it —
with gates that fail closed on accessibility, parity and originality.

Seven agent skills and seven tools. No native engines, no fork-a-template, no
credentials, no crawler. Python stdlib plus Playwright.

> *Leia em [português](README.pt-BR.md).*

## Why this exists

I scanned the reverse-engineering skills trending on GitHub —
[REA](https://github.com/morluto/rea) (333k stars),
[replica-skill](https://github.com/Jakeschincariol/replica-skill),
[ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template),
[reverse-skill](https://github.com/zhaoxuya520/reverse-skill) — and each one has
a piece of the answer. The full write-up is in
[`docs/RESEARCH.md`](docs/RESEARCH.md).

- **REA** has the discipline: Evidence IDs, observation kept separate from
  inference, a finding ledger. It targets binaries and needs Ghidra or IDA.
- **replica-skill** has the pipeline and the clean-room ethics. Its recon reads
  help docs and marketing pages, so the build sits downstream of *inference*.
- **ai-website-cloner** has the one idea that matters most — `getComputedStyle`
  instead of "about 14px, I think". It is visual-only and has no data model.

Nobody had combined them. Blueprint is that combination, pointed at the target
most people actually want to rebuild: a public web app.

**The thesis.** Clones come out wrong because a value enters the build as a
guess and nothing downstream can tell. So:

1. **Measure, never guess.** If the browser didn't report it, it isn't a value.
2. **Nothing enters a spec without an Evidence ID.** The ledger hashes every
   raw capture, so any claim can be re-checked against its bytes.
3. **`observed`, `inferred` and `chosen` are different words.** Divergence is
   the point of a rebuild — but it is never disguised as an observation.
4. **Verify with the same instrument.** Capture your own build exactly as you
   captured the target, then score the two derived systems against each other.
5. **Gates fail closed.** A guard rail you can ignore by default is decoration.

## Install

```bash
# as a Claude Code plugin
/plugin marketplace add tassiorj25/tassiorj25
/plugin install blueprint@blueprint

# or copy the skills in
git clone https://github.com/tassiorj25/tassiorj25 blueprint
cp -r blueprint/skills/bp-* ~/.claude/skills/     # or .claude/skills/ in a project
```

Requirements: Python 3.9+ (stdlib only), Node 18+, and Playwright for capture.
Pillow is optional and only used by the visual diff.

```bash
npm install playwright && npx playwright install chromium
```

## The pipeline

```
bp-recon  →  bp-tokens  →  bp-model  →  bp-spec  →  bp-build  →  bp-verify  →  bp-brand
 measure     design         data        exact       code        score         ship gate
             system         model       specs
```

Each step writes into `blueprint/` in your project and reads what came before.
Any step also runs on its own.

| Skill | Does | Writes |
|---|---|---|
| `bp-recon` | captures evidence, maps screens and flows | `evidence/`, `recon.md`, `findings.md` |
| `bp-tokens` | clusters measured styles into tokens; contrast gate | `tokens.json`, `tokens.css` |
| `bp-model` | entities from response shapes, collections from DOM | `model.json`, `model.md` |
| `bp-spec` | component specs with exact values and citations | `spec/*.md` |
| `bp-build` | builds from specs, your content | your codebase, `divergences.md` |
| `bp-verify` | parity score + visual diff, gated | `parity.json`, `verify.md` |
| `bp-brand` | originality sweep — fails closed | `sweep.json`, `ship.md` |

## The tools

Each runs standalone. `--help` on any of them.

```bash
# measure a page: computed styles, DOM boxes, response shapes, assets
node tools/capture.mjs --out blueprint/evidence --viewports 390,1440 https://target.test/

# every raw file re-hashed; fails if one changed after capture
python3 tools/ledger.py --dir blueprint/evidence verify

# cluster what was measured into a design system
python3 tools/tokens.py --dir blueprint/evidence --out blueprint/tokens.json --css blueprint/tokens.css

# WCAG check over the derived palette
python3 tools/contrast.py --tokens blueprint/tokens.json --gate

# entities, fields, relationships, endpoints
python3 tools/model.py --dir blueprint/evidence --out blueprint/model.json

# score your build against the target, from evidence on both sides
python3 tools/parity.py --target blueprint/evidence --clone blueprint/clone-evidence --gate 80

# pixel diff with a heatmap and per-band scores
python3 tools/imgdiff.py target.png clone.png --heatmap diff.png

# the ship gate: brand, host, verbatim copy, asset URLs
python3 tools/sweep.py --dir blueprint/evidence --source .
```

### What the output looks like

Against [news.ycombinator.com](https://news.ycombinator.com), one page, one
viewport:

```
$ python3 tools/model.py --dir blueprint/evidence
  dom_collections_inferred: 10
  → tr.athing.submission   rows=30  uniform_w=1.0
      slot span.rank   x1 → label
      slot td.votelinks x1 → container
      slot a           x3 → link
```

It found the 30 story rows and what each one renders, with no API to read.

```
$ python3 tools/contrast.py --tokens blueprint/tokens.json
   3.54  AA-large-only  #828282  on #f6f6ef  (x657)
```

That is a real accessibility finding about the real target — the sort of thing
you want to *not* inherit.

```
$ python3 tools/parity.py --target ... --clone ...
overall parity  63.44/100
  palette     91.32    type   67.90    spacing  35.20
  shape      100.00    structure  32.99
  unmatched spacing step 6px (used x30)
```

The breakdown is the useful part: this clone got the colours and missed the
grid.

## Boundaries

`capture.mjs` enforces these rather than documenting them:

- **robots.txt decides**, and a `Disallow` match has **no override**. An
  unreachable `robots.txt` refuses too, rather than assuming permission.
- **No crawler.** You pass the page list; `--max-pages` caps it.
- **No credentials.** There is no such code path.
- **Shapes, not payloads.** JSON bodies are reduced to key/type schemas in the
  browser, before anything is written, so real user data never reaches disk.
- **Assets are inventoried, never downloaded.**

And `sweep.py` fails closed on the target's brand, domain, verbatim copy and
asset URLs — including a brand split across lines and a partial lift of a
paragraph.

What no tool can decide for you — terms of service, trade dress, trademark,
licences — is in [`docs/LEGAL.md`](docs/LEGAL.md). A clean sweep is not
clearance.

## Tests

104 tests, no network, no browser, no pip install.

```bash
python3 tests/run.py                      # 86 Python tests
node --test tests/capture-rules.test.mjs  # 18 Node tests
```

They cover the things that would quietly rot: WCAG ratios against the spec's
own reference values, tamper detection on the ledger, robots.txt precedence
including `Allow` carve-outs and named agent groups, that `jsonShape` never
emits a payload value, and that parity reports a mismatched base unit instead
of averaging it away.

## Licence

MIT. See [LICENSE](LICENSE).

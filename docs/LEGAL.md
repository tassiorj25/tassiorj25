# Boundaries

Not legal advice. This file describes what the tools enforce and what they
cannot, so you know which is which.

## What Blueprint rebuilds

**Behaviour and interaction patterns**, measured from public pages. How a flow
is sequenced, what a layout does at a breakpoint, what shape an API returns,
what a list row shows. Functional behaviour and interface conventions are
generally not protectable the way creative expression and marks are — which is
why this pipeline is built around behaviour and refuses the rest.

## What it never touches

- **Source code.** No bundles, no decompilation, no minified sources.
- **Marks.** Name, logo, wordmark, trade dress. The sweep fails closed on them.
- **Copy.** Captured strings are reference material for the sweep, never input
  to the build. Partial lifts are caught too.
- **Assets.** Images, icons, fonts, illustrations. The inventory records that
  an asset exists; it never downloads it.
- **Content.** Catalogue, listings, user-generated data. You can rebuild the
  player; the library is not part of it.
- **Anything behind authentication.** There is no credential handling in this
  codebase at all.

## What the tools enforce

| Boundary | Enforced by | Overridable |
|---|---|---|
| robots.txt `Disallow` | `capture.mjs` refuses the page | **no** |
| unreachable robots.txt | `capture.mjs` refuses rather than assuming | **no** |
| no crawling | you pass the page list; `--max-pages` caps it | by raising the cap |
| no payload capture | bodies reduced to shapes in the browser | **no** |
| no credentials | no such code path exists | **no** |
| evidence integrity | `ledger.py verify` rehashes every raw file | **no** |
| contrast | `contrast.py --gate` | by dropping `--gate` |
| no traces of the target | `sweep.py` exits non-zero on any finding | `--warn-only`, `--allow` |

Rate limiting is a sequential capture with a default 1.5s pause, and a
user-agent that identifies the tool. It is polite, not a guarantee — a large
page list at a low `--delay` is still load you are putting on someone else's
server.

## What no tool can decide for you

- **Terms of service.** If the terms forbid using an account to build a
  competing product, that is a decision, not a finding. `bp-recon` asks you to
  check and write it down.
- **Trade dress.** Layout plus colour plus icon set can read as the target with
  every string replaced. A person has to look at both and judge.
- **Trademark.** A clean sweep says nothing about whether *your* new name is
  free. Search the registers in your market.
- **Licences.** Icon sets, illustrations and fonts are licensed work. Licensed
  for their site is not licensed for yours.
- **Patents.** Out of scope for every tool here.

## If you are the target

Open an issue. If a capture path should be off limits, `robots.txt` already
stops it — `capture.mjs` honours `Disallow` with no override and refuses when
it cannot read your `robots.txt` at all.

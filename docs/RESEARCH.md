# Deep scan: what the trending reverse-engineering skills actually do

Scanned 2026-10-19. Star counts are what GitHub reported that day; they move
fast and third-party aggregators disagreed with GitHub on several of these, so
the numbers below are from the repository pages themselves except where noted.

## The four projects that matter

### morluto/rea — 333.6k stars

"One MCP for reverse engineering across binaries, applications, and runtime
behavior." An MCP server plus a `rea` CLI, installed with `npx rea-agents
setup`. Native analysis delegates to external engines — Hopper, Ghidra, IDA,
Kuna, JEB — and targets run from ELF/PE/Mach-O through Go and Rust binaries,
WASM, EVM bytecode, .NET assemblies, Android APKs, Flutter, firmware, SQLite
and packet captures.

What is worth taking is not the tooling, it is the **discipline** in its
`reverse-engineer-anything` skill:

- every result carries an **Evidence ID**, and conclusions cite them;
- **observation, inference and unknown** are kept distinct, with an explicit
  rule never to imply that static analysis observed execution;
- a **finding ledger** links each conclusion to evidence, confidence and
  what remains unknown;
- **summary-first** working: smallest useful overview, then follow specific
  hypotheses, and no repeating a call that already failed;
- it tells the agent to **not** use it for ordinary source-repository
  analysis.

What limits it for "see how apps are built and build ours": it points at
binaries and firmware, needs heavyweight native engines installed, and stops
at explaining. It does not take you to a working rebuild.

### Jakeschincariol/replica-skill — 3.5k stars

Eleven Claude skills — `recon`, `architect`, `design`, `build`, `backend`,
`test`, `diff`, `entrepreneur`, `brand`, `launch`, `deploy` — chained through a
`replica/` folder, each reading the previous step's output. MIT.

The right shape, and the right ethics. Its framing: it "rebuilds what an app
does, never what it owns", clean-room, public sources and your own account
only, rebranding mandatory before launch and deploy blocked until the sweep
passes, features and flow but never the catalogue.

Where it is weak: **recon is documentary**. It reads help docs, pricing pages,
changelogs, app-store listings, marketing and videos, then infers a data model
with confidence levels. It explicitly refuses to read JS bundles or private
network calls. That keeps it safe, but it means the single highest-value signal
— what the browser actually computed and rendered — is left on the table, and
the build is downstream of inference rather than measurement.

### JCodesMore/ai-website-cloner-template — 13k–26k stars (sources disagree)

`/clone-website <url>` in five phases: screenshots at several breakpoints and
style sweeps over visible elements; tokens written into the global stylesheet;
component specs carrying exact `getComputedStyle()` values, interaction models
and breakpoints; parallel builders each in their own git worktree; assembly and
visual diff against the original. Next.js 16 + React 19 + Tailwind v4.

This one contains the single best idea in the whole field: **measure, don't
guess**. `getComputedStyle` turns "about 14px, I think" into 13.3333px. It is
why its output is tight where prompt-only cloning is loose.

Its limits: it is a template you fork rather than a portable skill, it is
visual-only — no data model, no API surface, no backend — and its verification
is a visual diff, which cannot distinguish "the right picture built from the
wrong elements" from a real rebuild.

### zhaoxuya520/reverse-skill — 42.7k stars

A 76-skill router pack for reverse engineering, authorised penetration testing
and security research, with on-demand toolchain bootstrapping. Strong in its
own lane; that lane is offensive security, not product rebuilding, so it is out
of scope here.

## Where the gap is

| | evidence is measured | data model | objective gate | portable | no native deps |
|---|---|---|---|---|---|
| rea | yes, binaries | no | no | plugin + engines | no |
| replica-skill | no, documentary | inferred | visual + manual | yes | yes |
| ai-website-cloner | **yes** | no | visual only | fork a template | yes |
| zhaoxuya520 | yes | no | no | yes | bootstraps |

Nothing in the field combines REA's evidence discipline with the website
cloner's measurement and replica-skill's clean-room pipeline. That combination
is what Blueprint is.

## The thesis

The reason clones come out wrong is not weak models. It is that **the value
enters the build as a guess, and nothing downstream can tell**. Fix that at the
seam:

1. **Measure, never guess.** `getComputedStyle`, measured boxes, response
   shapes. If the browser didn't report it, it isn't a value.
2. **Nothing enters a spec without an Evidence ID**, and the ledger hashes
   every raw capture so a claim can be re-checked against its bytes.
3. **Observed, inferred and chosen are different words** and the output keeps
   them apart. `chosen` is first-class — divergence is the point of a rebuild —
   but it is never disguised as an observation.
4. **Verify with the same instrument.** Capture your own build exactly as you
   captured the target, then score the two derived systems against each other.
   Symmetry is what makes the number mean something.
5. **Gates that fail closed.** Contrast, parity and the originality sweep all
   exit non-zero. A guard rail you can ignore by default is decoration.

## What was deliberately not built

- **Binary, APK and firmware analysis.** REA has it, it needs Ghidra or IDA,
  and it is not what "see how apps are built and build ours" means.
- **Anything behind a login wall.** No credential handling exists in this
  codebase, by design.
- **A crawler.** You pass the page list. `--max-pages` caps it.
- **Payload capture.** JSON bodies are reduced to key/type shapes in the
  browser, before anything is written, so real user data never reaches disk.

## Sources

- [morluto/rea](https://github.com/morluto/rea) ·
  [its reverse-engineer-anything SKILL.md](https://github.com/morluto/rea/blob/main/.agents/skills/reverse-engineer-anything/SKILL.md)
- [Jakeschincariol/replica-skill](https://github.com/Jakeschincariol/replica-skill) ·
  [its replica-recon SKILL.md](https://github.com/Jakeschincariol/replica-skill/blob/main/replica-recon/SKILL.md)
- [JCodesMore/ai-website-cloner-template README](https://cdn.jsdelivr.net/gh/JCodesMore/ai-website-cloner-template@master/README.md)
- [zhaoxuya520/reverse-skill](https://github.com/zhaoxuya520/reverse-skill)
- [InfoQ on REA and agent-driven binary analysis](https://www.infoq.com/news/2026/10/reverse-engineer-anything/)
- [Vercel, State of agent skills](https://vercel.com/blog/state-of-agent-skills)
- [Hugging Face, an analysis of the agent-skills marketplace](https://huggingface.co/blog/zhongshsh/agent-skills-analysis)

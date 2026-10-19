---
name: bp-model
description: >
  Infer the data model and API surface of a target app from observed JSON
  response shapes and repeated DOM structure, separating what was observed from
  what was inferred. Step 3 of Blueprint. Use after bp-recon when you need
  entities, fields, relationships or endpoints before building a backend.
---

# bp-model

Two signals, and the difference between them matters more than either.

**Observed** — JSON response shapes. An endpoint path names a resource, its
keys and types are its fields. This is close to reading the real schema.

**Inferred** — repeated DOM structure. Three or more siblings with the same
signature and uniform geometry is a collection; the slots inside a row are the
fields that row renders. You learn *that* a list of things exists and *what a
row shows*. You do not learn field names, and must not pretend otherwise.

## Run it

```bash
python3 tools/model.py --dir blueprint/evidence --out blueprint/model.json
```

Read `summary` first:

- `entities_observed: 0` with `endpoints_seen > 0` usually means the app is
  server-rendered. That is normal — work from `dom_collections`.
- `json_endpoints_with_shape` well below `endpoints_seen` means most traffic
  was assets. Capture the screens where data loads, and interact with them
  (open a list, page it) so the fetches actually happen.
- a non-empty `unknowns` is the honest part of the output. Carry each item into
  `findings.md`; do not resolve one by guessing.

## Build the model

Write `blueprint/model.md`:

**Entities.** One section each. Fields as a table: name, type, status
(`observed` / `inferred` / `chosen`), evidence, notes. A field you need but
never saw is `chosen` with empty evidence — that is a design decision, and it
should be visible as one.

**Relationships.** `model.json` proposes `belongs_to` from `*_id` fields and
`embeds` from nested keys, with `basis` naming why. Check each: a
`target_observed: false` relation points at an entity you never saw, so either
capture it or drop the relation.

**Endpoints.** Method, path, query keys, status, and what it appears to do.
Note which are read and which write — and remember you only observed reads.
Write paths are inference unless you watched your own account perform them.

**Cardinality and constraints are not in the evidence.** Whether a user has one
workspace or many, what is required, what is unique, how pagination is bounded
— none of that is visible from the outside. Decide it, and mark it `chosen`.

## Then design your own schema

Do not transcribe. Sketch the schema you would write knowing the shape of the
problem the target solved, and note where you diverge:

- a field the target seems to carry for legacy reasons — drop it;
- a denormalisation that exists for their scale and not yours — normalise it;
- a constraint you want that they apparently lack — add it, and say so.

The target's schema is evidence about the problem, not a specification.

## Finish

Append to `blueprint/findings.md`: entities and their status, the relationships
you accepted and rejected, every `chosen` decision, and what stayed unresolved.
Then hand off to `bp-spec`.

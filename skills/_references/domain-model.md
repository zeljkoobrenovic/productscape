# Product Domain Model — Shared Reference

Single source of truth for the structure, IDs, cross-file references, and the
validate→regenerate loop that every `edit-*` / `new-product-domain` skill relies on.
Skills link here instead of duplicating schema. Read this once per session before
editing any artifact.

## Repository shape

```
_config/product-domains/<group>/<domain>/   JSON source of truth (edit here)
_templates/<area>/                   HTML templates (presentation only)
_wiring/product-domains/             Python generators (logic; do not edit for content)
docs/<group>/<domain>/       Generated output (never hand-edit)
```

Always put domains in a group. Groups are discovered dynamically and may change;
domain IDs must remain globally unique. `_config/product-domains/start/` contains
shared navigation and is excluded from discovery. Use `_wiring/domain_paths.py`
to resolve source folders and published paths. CLI arguments use the bare domain ID; published URLs include the current group.

Pipeline is one-directional: `_config + _templates --(Python in _wiring)--> docs`.
No framework, no build system, no npm. Generators `shutil.rmtree` their target
docs folder before rebuilding, so **never** hand-edit `docs/**`, and inspect a
dirty worktree before regenerating.

## Live artifacts (the set these skills cover)

| Artifact | File(s) | Generator |
|---|---|---|
| Start / domain config | `start/config.json` | `generate-start-docs.py` |
| Customers | `customers/customers.json`, `customers/insights.json`, `customers/links.json`, `customers/relations.json` | `generate-customers-docs.py` |
| Products & deployment | `product-deployments/products.json`, `deployment.json` | `generate-products-docs.py` |
| Product bricks | `product-bricks/product-bricks.json` | `generate-product-bricks-docs.py` |
| Streams | `product-bricks/product-stream.json` | `generate-product-bricks-docs.py` |
| Data assets | `data/data-assets.json` | `generate-product-bricks-docs.py` |
| Teams | `teams/teams.json` | `generate-teams-docs.py` |
| Competition | `business/competition.json` | `generate-competition-docs.py` |
| Domain brief | `_domain/DOMAIN.md` | (narrative, not generated) |

## ID conventions (enforced by `validate-domain-model.py --strict-ids`)

- Every `id`, `*Id`, `*Ids`, `objectId` value in `_config/**` is **lowercase**,
  matching `^[a-z0-9][a-z0-9._:-]*$`. Exceptions: `evidence-ids` values and
  `keyResultId` may contain regex/path-like characters.
- Customer / brick IDs are short stable codes (`ridu`, `drvu`, `trip`, `disp`).
  Stream / asset / team / insight IDs are hyphenated slugs
  (`rider-book-and-complete-a-reliable-trip`, `customer-profile`, `rider-core`,
  `rsm-01`).
- Product-brick **module** IDs must start with `module-`.
- IDs are stable: renaming an ID breaks every cross-file reference to it.

## Cross-file reference map (the integrity that must hold)

```
customers.json
  customer.id ─────────────┬─▶ insights.json     linkedCustomers[].customerId
                           ├─▶ products.json      portfolio.products[].primaryCustomers[].id
                           └─▶ teams.json         ...teams[].customerDependencies[].customerId
  jobsToBeDone[].id ───────┬─▶ insights.json     linkedCustomers[].jobIds[]
                           └─▶ customerJourneyStories[].linkedJobIds[]
  jtbd.steps[].streamsNeeded[].id ─▶ product-stream.json  stream id (or brick id)
  kpiPyramids ... node ids ─▶ insights.json linkedCustomers[].kpiIds[] (by ID)
  kpiPyramids ... names ───▶ teams.json metrics, productStrategy northStar/supporting (by NAME — legacy)

product-bricks.json
  brick.id ────────────────┬─▶ deployment.json     ...deployedBricks[].brickId
                           ├─▶ product-stream.json brickDependencies[].targetBrickId, flows steps deps
                           └─▶ teams.json          ...brickDependencies[].brickId
  brick.dataDependencies[].assetId ─▶ data-assets.json  asset.id
  brick.layers[].modules[].id (module-*) ─▶ referenced by brickDependencies[].moduleId

products.json
  portfolio.products[].id ─▶ deployment.json ...deployedBricks[].usedInProducts[].productId

deployment.json
  channels[].channels[].deployedBricks[].brickId ─▶ product-bricks.json brick id

data-assets.json
  asset.ownerTeamId ───────▶ teams.json team id
```

When you add or rename an entity, update **every** referencing file in the same
edit. The validator catches brick/team/module breakage; customer- and
asset-level references you must check by hand (see each `edit-*` skill).

## Product-brick layer model (fixed)

`PRODUCT_BRICK_LAYER_ORDER` = `ui → interfaces → worker → stateless-service → service → integration`.

Module `type` must be one of:
`web-component, mobile-component, bff, api, backoffice-interface, message-queue,
message-consumer, daemon, stateless-service, stateful-service, service, integration`.

`metadata.modulesConfig.layerTypes` / `moduleTypes` (when present) must match these
sets exactly, and each module type needs a `color`. The shared defaults live in
`_config/_shared/product-brick-model.json` (same for `brickTypes`/`brickStatuses`,
and `teamTypes`/`teamDependencyTypes` in `team-model.json`, stream `definitions` in
`product-stream-model.json`) — domain files only declare these blocks to override
the shared model. Source of truth for the fixed sets:
`_wiring/product-domains/product_bricks_support.py`.

## Customer journey model (fixed)

`customerJourneyStories[].stages[].stage` values are the fixed adoption lifecycle:
`Trigger → Discovery → Evaluation → Trial → Engagement → Retention` (exactly these
six, in order). A journey describes how the persona adopts and stays with the
**product** — never a walkthrough of their work tasks (that belongs in JTBD steps
and streams). See `edit-customers` for per-stage definitions.

## Customer relations model

`customers/relations.json` (optional per domain) declares directed customer-to-
customer relations rendered as a diagram + filterable table on the customers page:
`relationTypes[]` (standard ids `commercial`, `operational`, `financial`,
`information`) and `relations[]` with `from`/`to` = customer ids, `type`, `name`,
`description`, optional `streamIds[]` = stream ids. Every id must resolve;
`transport-management-and-freight-exchange` is the exemplar.

## KPI pyramid model (fixed)

`customers.json` → each persona's `kpiPyramids` holds a `customerOutcomes` and
(usually) a `businessOutcomes` pyramid. A pyramid is `top` + `branches[]`, each node
having `children[]`.

- **Shape invariant: every non-leaf node has ≥2 children; a leaf has `children: []`.
  Never exactly one child, at any level.** A `top → 1 branch → 1 child → 1 leaf` chain
  is a line, not a pyramid — the most common authoring mistake.
- **Target: 4 levels** — `top → 2 branches → 2 mid metrics each → 2 leaves each`
  (1 + 2 + 4 + 8 = 15 nodes). A 3-level `top → 2 branches → 2 leaves` is acceptable only
  when diagnostics are genuinely sparse. Don't pad with vanity metrics to hit a count.
- KPI **ids** are unique within a persona (across both pyramids). `insights.json`
  links KPIs by **id** (`linkedCustomers[].kpiIds[]` — the validator checks these
  resolve; never use the legacy name-based `kpis` field in new content). `teams.json`
  metrics and the persona's `productStrategy` `northStar`/`supporting` still link by
  NAME — every such name must exist as a node in that persona's pyramids
  (`check-kpi-pyramids.py` reports violations). The customer landing page shows
  "No KPI pyramid defined" unless BOTH pyramids are present. See `edit-customers`
  for the full schema.

## Validate and regenerate

Run from the data project root:

```sh
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py check-kpis my-domain
python3 productscapes.py build my-domain
```

The toolkit owns the schemas under `_config/_schema/` and the generator code.
Use the project launcher to select the correct source and output directories.
See [workspace paths](workspace.md) for the repository boundary.

## Optional examples

The separate productscape-examples repository contains `maas` (teams and product
usage), `ride-sharing-marketplace` (customers, bricks, streams, data, competition),
and other domains of varying maturity. Compare them when available. The toolkit's
schemas and starter establish the contracts even when no examples are cloned.

## Working principles (apply to all edits)

- Source JSON first; presentation in templates; `docs/**` is output.
- Separate sourced facts from assumptions and inference. Don't invent business
  metrics or source-backed claims. Use official URLs for competition stats.
- Reuse existing JSON schemas and `${...}` template patterns; don't invent parallel
  structures.
- Keep domain language: customers, product deployments, product bricks, streams,
  teams, data assets, competition, and evidence.
- Every entity must earn its place — a segment/brick/team that doesn't change a
  decision should be merged or dropped.

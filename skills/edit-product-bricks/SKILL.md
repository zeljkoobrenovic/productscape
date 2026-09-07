---
name: edit-product-bricks
description: "Create or edit product bricks for a product domain: root groups, subgroups, bricks, their layered modules (ui/interfaces/worker/stateless-service/service/integration), brick-to-brick dependencies, data dependencies, and external-system dependencies in _config/product-domains/group/domain/product-bricks/product-bricks.json. Use when adding a brick, restructuring brick groups, adding/moving modules across layers, wiring module or brick dependencies, or linking bricks to data assets. Keeps brick and module IDs consistent across products, deployment, streams, teams, evidence, and data assets."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Product Bricks

Authoring skill for `product-bricks/product-bricks.json` — the implementation-facing
architecture and the most cross-referenced artifact in the model. Combines the
brick-architecture methodology with this repo's exact schema and the
validate→regenerate loop. Read [domain model](../_references/domain-model.md) first, and
**read the existing file plus the relevant toolkit schema (optionally compare `ride-sharing-marketplace` in productscape-examples)
(20 bricks across 3 levels) before editing** — match its shape and depth.

The product-bricks validator is strict (see `validate-domain`): get the schema exactly
right or generation/validation fails.

## Method (what good looks like)

- **Bricks are buildable, ownable units** that connect customer value → roadmap →
  delivery → systems → data → teams. Not vague aspirations, not tiny tasks; they
  sound like product/platform building blocks.
- **Three meaningful levels**: root group (durable product/platform area) → subgroup
  (related workflows/systems) → brick. A mature domain has **20+ bricks**.
- Every brick must be able to have an **owning team** and trace to a customer or
  business outcome. A brick referenced by no product/stream/team is an orphan — drop
  or wire it.
- **Modules live under `layers`** by architectural responsibility, not as a flat list.
  Only include a layer when it has modules.
- Keep module and brick IDs **stable** — dependencies refer to them by ID.
- Name external systems by role or provider category where exact vendor isn't
  warranted. Don't invent dependencies to fill fields.

## Exact schema

### Top level

```json
{ "metadata": { … }, "rootGroups": [ … ] }
```

### metadata (governs rendering, filtering, and validation)

```json
{
  "title": "Product Bricks & Streams",
  "description": "…",
  "rendering": { … },
  "brickTypes":   [ { "id": "full-stack", "name": "full-stack brick", "color": "#b6d7a8ff" }, … ],
  "brickStatuses":[ { "id": "invest", "name": "invest", "color": "blue" },
                    { "id": "sustaining", … }, { "id": "sunset", … } ],
  "modulesConfig": {
    "layerTypes":  [ { "id": "ui", "name": "ui", "description": "…",
                       "hostsModules": ["web-component","mobile-component"] }, … ],
    "moduleTypes": [ { "id": "web-component", "name": "web component",
                       "description": "…", "color": "#dbeafe" }, … ]
  }
}
```
> `brickTypes`/`brickStatuses`/`modulesConfig` normally come from the shared model
> `_config/_shared/product-brick-model.json` — OMIT them in domain files unless the
> domain genuinely diverges (a local value overrides the shared one). Never use
> legacy `types`/`statuses`.
> `modulesConfig.layerTypes` must cover exactly the six layers and `moduleTypes` the
> twelve module types below, each `moduleType` with a `color`. The validator rejects
> mismatched sets or missing colors.

### rootGroups → subGroups → bricks

```json
{
  "rootGroups": [
    {
      "name": "Rider Demand and Trip Experience",   // groups use name, NOT id
      "description": "…",
      "subGroups": [ { "name": "…", "description": "…", "bricks": [ … ] } ],
      "bricks": [ … ]                                 // bricks may sit directly on a group too
    }
  ]
}
```

### brick object

```json
{
  "id": "trip",                          // lowercase short stable code
  "name": "Trip Request and Intent Capture",
  "type": "full-stack",                  // → metadata.brickTypes[].id
  "status": "sustaining",                // → metadata.brickStatuses[].id
  "description": "…",
  "links": [                                  // grouped; rendered in the Links tab
    { "group": "Evidence", "description": "…",
      "links": [ { "label": "Evidence Explorer",
                   "link": "../../../../evidence-explorer/index.html",
                   "description": "…",
                   "embedLink": "../../../../evidence-explorer/index.html?embed=1",  // optional: renders an iframe
                   "embedHeight": 400 } ] }    // optional; iframe height in px, default 400
  ],
  "layers": [ … ],
  "brickDependencies": [ … ],
  "dataDependencies": [ … ],
  "externalSystemsThisBrickDependsOn": [ … ],
  "externalSystemsDependingOnThisBrick": [ … ]
}
```

### layers[] and modules[]

```json
{
  "layer": "ui",                         // one of the six; see layer→type map
  "description": "…",
  "modules": [
    {
      "id": "module-request-ux-surface", // MUST start with module-, lowercase, unique in brick
      "name": "Request UX Surface",
      "type": "web-component",           // → metadata.moduleTypes[].id, valid for this layer
      "description": "…",
      "dependencies": {                  // optional
        "modules": [
          { "moduleId": "module-quote-api", "type": "uses", "description": "…" }
        ]
      }
    }
  ]
}
```

**Layer → allowed module types (fixed order `ui → interfaces → worker → stateless-service → service → integration`):**

| layer | hostsModules |
|---|---|
| `ui` | `web-component`, `mobile-component` |
| `interfaces` | `bff`, `api`, `backoffice-interface` |
| `worker` | `message-queue`, `message-consumer`, `daemon` |
| `stateless-service` | `stateless-service` (orchestration only; aggregates services, owns no durable state) |
| `service` | `stateful-service`, `service` |
| `integration` | `integration` |

> A `dependencies.modules[]` entry that targets a module in **another** brick adds
> `"targetBrickId": "<brick>"` alongside `moduleId`. Same-brick deps omit it.

### brickDependencies[] (brick → brick)

```json
{
  "targetBrickId": "trip",                 // → another brick's id
  "moduleId": "module-trip-request-api",   // a module in targetBrickId
  "sourceModuleId": "module-support-workflow-api", // a module in THIS brick
  "type": "context",
  "description": "…"
}
```
> Do NOT use the legacy `interface` field. If `targetBrickId` is set, `moduleId` is
> required and must exist in the target brick; `sourceModuleId` must exist in this brick.

### dataDependencies[] (brick → data asset)

```json
{
  "assetId": "trip-request-and-intent-capture",   // → data-assets.json asset id
  "moduleIds": [ "module-issue-intake-and-classification", … ], // modules in THIS brick
  "role": "own",                                  // relationship verb; own = system of record.
                                                  // seen across domains: own, read, write, read-write,
                                                  // consume, publish, query, enrich, govern, store
  "description": "…"
}
```
> Required `moduleIds` when `assetId` is set; each must be a real module in this brick.
> Do NOT use `storeIds` here — stores live in the data-asset catalog.

### external system dependencies

```json
// outbound
"externalSystemsThisBrickDependsOn": [
  { "system": "Maps and geocoding providers", "type": "data",
    "interface": "Location API", "description": "…",
    "sourceModuleId": "module-request-capture-and-validation" } // module in THIS brick
],
// inbound
"externalSystemsDependingOnThisBrick": [
  { "system": "Rider applications", "type": "channel-consumer",
    "interface": "Trip Request API", "description": "…",
    "moduleId": "module-trip-request-api" }                     // module in THIS brick
]
```

## Cross-file rules to keep intact

When you add/rename a **brick id**, update every referencing file:
- `product-deployments/products.json` → `portfolio.products[].neededBricks[].brickId`
  (and `brickName`)
- `product-deployments/deployment.json` → `…deployedBricks[].brickId` (and `brickName`)
- `product-bricks/product-stream.json` → `…brickDependencies[].targetBrickId` and
  flow `steps[].dependencies[]` of `type:"brick"`
- `teams/teams.json` → `…teams[].brickDependencies[].brickId`

When you add/rename a **module id**, fix any `brickDependencies[].moduleId/sourceModuleId`
and `dependencies.modules[].moduleId` (in this and other bricks) that point at it, plus
`dataDependencies[].moduleIds` and external-system `sourceModuleId/moduleId`. When you
add a `dataDependencies.assetId`, it must exist in `data-assets.json` (add it with
`edit-data-assets` if not).

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`
   — this validator deeply checks bricks: layers/module-types, `module-` prefix,
   duplicate brick/module IDs, resolvable module/brick/data dependencies, legacy
   fields, and `modulesConfig` correctness. Fix every error before proceeding.
   (It does NOT check products/deployment/stream/team back-references to bricks —
   verify those by hand or with `audit-domain-balance`.)
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
   (also rebuilds stream/data-asset pages; name/description from the domain's `start/config.json`). Generator wipes the product-bricks docs folder — ensure that area's
   worktree is clean first.
3. Report bricks/modules added or changed, dependency wiring, and which referencing
   files you updated.

## Avoid

- A flat brick list where the model expects root groups + subgroups; duplicating one
  brick across groups.
- Root-level `interfaces` or `internalModules` on a brick (legacy — use `layers`).
- Module IDs not starting with `module-`; module types not valid for their layer.
- `storeIds` in `dataDependencies`; legacy `interface` field in `brickDependencies`.
- Architecture jargon with no customer/operating relevance; orphan bricks no
  product/stream/team uses; inventing external/data references to fill fields.

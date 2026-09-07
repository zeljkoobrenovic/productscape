---
name: product-domain
description: "Router and index for creating and maintaining Productscape domain data (customers, strategy, jobs-to-be-done, product vision, insights, competition, teams, product bricks, streams, data assets, product deployments). Use when the user wants to work on a product domain but the specific artifact isn't named, when they ask what's possible, or to understand the model, ID conventions, and the validate/regenerate loop before editing _config/product-domains/**."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Product Domain (router)

Entry point for authoring and maintaining product-domain data in this repo. Use it
to orient, pick the right specialized skill, and run the shared validate→regenerate
loop. For schema, ID rules, and the cross-file reference map, read
[domain model](../_references/domain-model.md) first — every skill below depends on it.

## What this models

Product strategy modeled as structured JSON under `_config/product-domains/<group>/<domain>/`,
compiled by plain-Python generators in `_wiring/product-domains/` into a static doc
site under `docs/`. No framework, no build system. Edit JSON in `_config/**`; treat
`docs/**` as generated output.

## Pick a skill

| You want to… | Skill |
|---|---|
| Build a complete new domain from scratch | `new-product-domain` |
| Add/edit customer groups, personas, JTBD, journeys, KPI pyramids, per-customer strategy, insights | `edit-customers` |
| Set domain framing, vision, cross-cutting strategy & KPIs, `start/config.json` | `set-domain-strategy` |
| Add/edit products, interfaces, deployment channels & environments | `edit-products` |
| Add/edit product bricks, layers, modules, brick/data dependencies | `edit-product-bricks` |
| Add/edit product streams and flows | `edit-streams` |
| Add/edit data assets, stores, classification, ownership | `edit-data-assets` |
| Add/edit teams, org design, topology, ownership | `edit-teams` |
| Add/edit the competitive landscape | `edit-competition` |
| Check integrity & realism / find gaps & imbalance | `audit-domain-balance` |
| Validate JSON + references and regenerate docs | `validate-domain` |

> All skills above exist. If unsure which applies, follow `_references/domain-model.md`
> plus this router, mirror the relevant toolkit schema (optionally compare `ride-sharing-marketplace` in productscape-examples), and always
> run `validate-domain` before regenerating.

## The loop (always)

1. Identify the domain and read the relevant existing JSON before changing it.
2. Make the smallest correct edit; update **every** cross-referencing file (see the
   reference map).
3. Run `validate-domain` (validator + cross-file checks).
4. Regenerate only the affected domain's docs.
5. Report what changed and what referenced files were updated.

## Scope note

The live artifact set is: start, customers (+insights), products/deployment,
product-bricks (+streams, +evidence), data-assets, teams, and competition.

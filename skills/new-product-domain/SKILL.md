---
name: new-product-domain
description: "Create and author a complete product domain using Productscapes: research, customers, strategy, products, bricks, streams, data assets, teams, competition, and validation. Use for a new domain from scratch; use the artifact skills for narrower edits."
---

# New product domain

Read [workspace paths](../_references/workspace.md) and the
[domain model](../_references/domain-model.md). This skill works in an empty toolkit
clone or a separate data project. Example domains are optional references, not a
prerequisite. Use the toolkit schemas and `_templates/domain/` for file shapes.

## Frame and scaffold

Identify the target business, customer value, scope, source links, group, and
lowercase domain ID from the request and available context. Ask only for missing
information that materially changes the model. Capture scope, source-backed facts,
assumptions, and open questions in `_domain/DOMAIN.md`.

From the project root, create the source tree:

```sh
python3 productscapes.py new my-domain --group my-group --name "My Domain"
```

Use the actual chosen ID, group, and name. For a new separate data project, run the
toolkit CLI with `--project /path/to/project`; it creates a thin launcher there.
The starter has empty collections and must be authored. A passing scaffold
validation is not evidence of a researched, complete product domain.

The [input prompt](NEW-DOMAIN-PROMPT.md) helps capture the target and research scope.
Choose depth appropriate to the business; a small domain need not match a mature
example's object counts. Research current claims from primary sources and record
source URLs. Do not invent facts, statistics, implementation evidence, or ownership.

## Author in dependency order

1. Use `set-domain-strategy` for the brief, scope, customer value, and strategic horizons.
2. Use `edit-customers` for customer groups, personas, JTBD, journeys, measurable KPIs,
   customer strategy, insights, and relationships. Establish the customer and job IDs.
3. Use `edit-product-bricks` for buildable capabilities and their layered modules.
4. Use `edit-streams` to connect customer outcomes with bricks and external systems.
5. Use `edit-data-assets` for data meaning, stores, governance, and brick dependencies.
6. Use `edit-products` for customer-facing products and their deployment channels.
7. Use `edit-teams` for ownership and the operating model; reconcile team and data
   ownership references with the earlier artifacts.
8. Use `edit-competition` for a sourced competitive landscape. Add evidence references
   where real evidence exists. Author residuality stressors when relevant to scope.

Read the relevant skill when entering its phase. Reconcile earlier artifacts when
later authoring changes an ID or relationship. The current deployment schema maps
bricks to products through `deployedBricks[].usedInProducts`; follow the contracts
instead of adding parallel fields from older examples.

## Check and build

```sh
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py check-kpis my-domain
python3 productscapes.py build my-domain
```

Validate after meaningful source edits. Build when the requested outcome includes
the website or requires rendering verification. Inspect existing generated changes
first. Use `audit-domain-balance` to review the finished model's traceability,
realism, and intentional gaps. Summarize scope, authored artifacts, evidence and
assumptions, validation/build results, and remaining model gaps.

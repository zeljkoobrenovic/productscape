---
name: set-domain-strategy
description: "Frame a product domain and set its cross-cutting strategy: the domain boundary and brief (_domain/DOMAIN.md), the start/config.json identity, and the vision/KPI/strategy-horizon coherence that spans customers, products, bricks, and teams. Use when defining or reframing a domain's scope, vision, north-star metrics, or 1/3/5-year strategic horizons — the strategy layer that the per-customer productStrategy and team metrics must align to. Registers the domain through start/config.json."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Set Domain Strategy

The framing and cross-cutting strategy skill. Unlike the `edit-*` skills (one artifact
each), this one sets the **domain boundary, identity, and strategic spine** that the
other artifacts must stay coherent with. Read
[domain model](../_references/domain-model.md) first, and inspect the relevant schemas; optionally compare existing
domains in productscape-examples plus the reference `ride-sharing-marketplace`.

## Method (what good looks like)

### Domain framing
- Inspect adjacent domains before choosing the boundary. Name the domain in **business
  language**, not implementation language.
- Define **core scope, adjacent scope, and explicitly excluded scope**, and the main
  value exchange (who gets value, who pays, who operates, what makes value
  repeatable).
- Confirm the domain can support customers, products, 20+ bricks, teams, and a
  competition landscape. ID is lowercase hyphen-case; display name is title case.

### Cross-cutting strategy
- Set a **vision** in terms of customer outcomes and business viability.
- Define differentiation, strategic focus, product themes, and major tradeoffs.
- Create **1/3/5-year horizons** that show sequencing — not the same theme thrice —
  each with focus, product theme, customer KPI (north-star + supporting), and business
  KPI. Acknowledge constraints (trust, regulation, liquidity, integration, reliability,
  operations) where they bind.
- KPI **names** must be reused verbatim across `customers.json` (kpiPyramids,
  productStrategy), `teams.json` (charter metrics), and `insights.json` (kpis).

## Where strategy lives (this repo has no single strategy file)

| Concern | File |
|---|---|
| Domain identity (id/name/description) | `start/config.json` |
| Domain brief / boundary narrative | `_domain/DOMAIN.md` (narrative markdown, not generated) |
| Per-customer vision & 1/3/5-year horizons | `customers/customers.json` → each persona's `productStrategy` (see `edit-customers`) |
| KPI pyramids (north-star/supporting/diagnostic) | `customers/customers.json` → `kpiPyramids` |
| Sourced strategic insights | `customers/insights.json` |
| Team-level metrics aligned to KPIs | `teams/teams.json` → `teamCharter.metrics` |
| Competitive positioning | `business/competition.json` |

### start/config.json

```json
{
  "id": "ride-sharing-marketplace",      // lowercase hyphen-case, matches folder name
  "name": "Ride Sharing Marketplace",    // title case
  "description": "The … domain covers …"
}
```

## Registering the domain

Registration is automatic: the CLI discovers every domain that has a
`start/config.json` with `id`/`name`/`description`. Create that file and you're
generating. Keep the name/description identical to `start/config.json`.

## Working the strategy across artifacts

Because strategy is distributed, setting it means coordinated edits:
1. Frame the domain under `_config/product-domains/<group>/<domain-id>/` (`_domain/DOMAIN.md` and `start/config.json`). The config file registers it automatically; group names are discovered from the filesystem.
2. Set per-customer vision/horizons and KPI pyramids via `edit-customers`.
3. Align team charter metrics via `edit-teams` and insights via `edit-customers`.
4. Verify horizons sequence and KPI names match everywhere (use `audit-domain-balance`
   → "KPI & strategy coherence").

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`.
2. Regenerate affected areas: at minimum
   `python3 productscapes.py build <domain-id>
   from the project root, plus customers/teams generators if you changed
   those.
3. Report scope decisions, the vision, the horizon sequence, and KPI-name alignment.

## Avoid

- Generic growth language; identical horizons repeated across years or personas.
- A domain boundary that's really a whole-company description.
- KPI names that drift between customers, teams, and insights.
- Mismatched id/name/description between `start/config.json` and the domain folder.

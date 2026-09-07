---
name: audit-domain-balance
description: "Review a product domain for realism, completeness, and balance — not just JSON validity. Use to assess whether a domain is high-quality and well-balanced: per-artifact density vs the reference domain, cross-segment coverage, brick-layer balance, team/brick ownership gaps, customer→brick→team traceability, research/source quality, and sparse vs over-built areas. Produces a prioritized gap report. Run before declaring a domain 'done' or when asked if a domain is mature/realistic/complete."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Audit Domain Balance

Goes beyond `validate-domain` (which checks JSON + reference integrity) to judge
whether a domain is **realistic, complete, and balanced**. Output is a prioritized
gap report, not file edits. Read [domain model](../_references/domain-model.md) for the
model and the reference-domain density targets.

## How to run the audit

1. **Validate first.** Run `validate-domain <domain-id>`. A domain that fails
   integrity isn't ready for a balance judgment — report failures up front.
2. **Establish the baseline.** Compare against `ride-sharing-marketplace` (the mature
   reference). Note that `audio-streaming-platform` is a known-sparse domain — a
   useful "what thin looks like" contrast, not a target.
3. **Score each dimension below**, with concrete counts and named gaps.
4. **Prioritize**: P1 = breaks realism or traceability; P2 = noticeable imbalance;
   P3 = polish. Recommend the specific `edit-*` skill to fix each.

## Dimensions

### Density vs reference
Count entries per artifact and compare to the reference domain (mature targets):
customer groups (~4) and personas, bricks (20+ across 3 group levels for a mature
domain), data assets (15+), teams (8+), competitors (8+), insights (8+). Flag
artifacts that are skeletal (1–2 entries where the reference has many) or absent.

### Cross-segment coverage
- Every customer group has personas with JTBD, journeys, KPI pyramids, and
  per-customer `productStrategy`. Flag personas missing any of these.
- Journey stories use the fixed adoption stages (Trigger, Discovery, Evaluation,
  Trial, Engagement, Retention) and describe adopting the product. **P1: flag any
  journey whose stages are task phases ("Preparation", "Award", "Dispatch"…) or
  whose narratives would read the same without the product — that's a JTBD
  narrative in journey clothing.**
- Multi-sided domains have distinct segments (buyer/user/operator/partner), not one
  generic "user". Flag collapsed segmentation.
- Each segment maps to at least one product and one owning team.

### Traceability chains (the spine of quality)
Walk the spine and flag breaks:
`customer → JTBD → stream/brick → product (neededBricks) → deployment → team (ownership)`
and `insight → linkedCustomers (customerId, jobIds) → kpis`.
- Customers with no products serving them.
- Bricks in `product-bricks.json` referenced by no product, stream, or team
  (orphan bricks) — and products needing bricks that don't exist.
- Bricks with no owning team; teams owning no bricks.
- Data assets with empty `ownerTeamId`, or assets referenced by no brick's
  `dataDependencies`.
- JTBD steps whose `streamsNeeded` point to non-existent streams/bricks.

### Brick-layer balance
- Bricks should distribute across the layer model
  (`ui → interfaces → worker → stateless-service → service → integration`), not all
  collapse into one layer.
- Flag bricks with no modules, or a domain where every brick is single-layer (often a
  sign of shallow modeling).
- Check brick/module dependency density is plausible (neither zero coupling nor a
  fully-connected graph).

### KPI & strategy coherence
- **Pyramid shape (P1 when broken): every non-leaf node has ≥2 children.** Flag any
  node with exactly one child — a `top → 1 branch → 1 child → 1 leaf` line is not a
  pyramid. Report the count of single-child nodes and where they are; a mature domain
  targets `top → 2 branches → 2 mid metrics each → 2 leaves each` (4 levels, 15 nodes),
  with a 3-level `top → 2 branches → 2 leaves` acceptable only when diagnostics are
  genuinely sparse.
- Every persona has both a `customerOutcomes` and (where business is modeled) a
  `businessOutcomes` pyramid — the customer landing page shows "No KPI pyramid defined"
  unless **both** exist.
- Measurable leaves with units; no vanity terminals or padding leaves.
- KPI **ids** unique within a customer; KPI **names** reused consistently across
  customers, teams, and insights, and every `northStar`/`supporting`/insight `kpis`
  name resolves to a node in that customer's pyramids.
- Per-customer and domain strategy horizons (1/3/5-year) are present and distinct,
  not copies.
- Targets are plausible, not arbitrary precision on unsourced numbers.

Quick shape check (run against the domain's `customers.json`):
```bash
python3 - "$DOMAIN" <<'PY'
import json,sys
sys.path.insert(0, '_wiring')
from domain_paths import resolve_domain_dir
d=json.load(open(resolve_domain_dir(sys.argv[1]) / 'customers' / 'customers.json'))
def walk(n,path,bad):
    k=len(n.get('children',[]))
    if k==1: bad.append(' > '.join(path+[n['name']]))
    for c in n.get('children',[]): walk(c,path+[n['name']],bad)
bad=[]
for g in d:
    for c in g['customers']:
        for key in ('customerOutcomes','businessOutcomes'):
            p=c['kpiPyramids'].get(key)
            if not p: continue
            if len(p['branches'])<2: bad.append(f"{c['id']}/{key}: top has {len(p['branches'])} branch(es)")
            for b in p['branches']: walk(b,[f"{c['id']}/{key}"],bad)
print('single-child / thin nodes:', bad or 'none — pyramids fan out ✓')
PY
```

### Research And Sourcing
- Competition stats carry official source URLs and reported scope; no invented
  metrics.
- Insights link to `sources[]` via `sourceIds` and to customers/jobs/KPIs.
- `customers/links.json` has useful link groups, relevance notes, and tags that
  support the modeled customer, market, product-surface, partner, or trust context.

### Over-build & redundancy
Imbalance cuts both ways: flag duplicated personas, near-identical bricks that should
merge, teams with no distinct mission, or detail in one artifact far exceeding the
rest (e.g., 30 bricks but 2 customers).

## Report format

```
# Balance audit: <domain-id>
Integrity: <pass | N errors — list>
Density vs reference: <table of counts>

## P1 — realism / traceability breaks
- <finding> → fix with `edit-<x>`
## P2 — imbalance
## P3 — polish

Overall: <one-line maturity judgment: skeletal / partial / mature>
```

Be specific and quantitative — name the customer, brick, or team. Avoid generic
advice like "add more detail".

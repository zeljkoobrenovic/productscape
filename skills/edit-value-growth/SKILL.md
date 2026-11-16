---
name: edit-value-growth
description: "Create or update a domain's Value & Growth business section: value and pricing metrics, selling motion, growth positioning, activation, market opportunity and unit economics. Use for business/value-growth.json and its customer, product and competitor references."
---

# Edit Value & Growth

Use [workspace paths](../_references/workspace.md) in a separate data project.
Read the existing domain brief, customers, products and competition before choosing
commercial segments. The source is `business/value-growth.json`; the toolkit owns
`_config/_schema/value-growth.schema.json` and `_templates/value-growth/`.
The page is `docs/<group>/<domain>/value-growth/index.html`, under Business.

## Modeling decisions

- Model an offering for a customer segment, rather than assigning one sales motion
  or growth strategy to an entire industry or company. Reuse customer, job, KPI,
  product and competitor IDs; explain when the user, buyer and payer differ.
- Distinguish the customer outcome, value unit, pricing unit and provider revenue.
  Seats, downloads and transactions are candidates, not automatic value metrics.
  Include the charging model and how a buyer could verify the claimed value.
- Keep bottom-up/top-down/hybrid selling separate from positioning. Dominant means
  better outcomes at a lower price; differentiated means better outcomes at a
  premium; disruptive means simpler and cheaper for overserved customers or
  nonconsumers. Name the alternative and conditions. Use mixed or unclassified
  where the evidence does not support a single position.
- Define first live value and repeated value. Signups, sandbox events and API calls
  may show progress without demonstrating a customer outcome. Distinguish product,
  sales and partner contributions; a distribution channel is not automatically a
  network effect.
- Use optional `entryStrategy` and each segment's `activation.entryOffer` to
  distinguish freemium, timed trials, sandbox access, paid pilots and usage-priced
  entry. Explain fit, evaluation scope, limits, the paid trigger and a cohort-based
  conversion measure. Separate the infrastructure buyer's offer from trials they
  configure for their own customers. Keep observed vendor terms separate from
  proposed packaging; no monthly fee does not establish free production usage.

## Evidence and market sizing

Read [the format guide](references/format.md) when authoring the JSON.
Every evidence block declares `observed`, `inferred` or `illustrative`, a short note
and source IDs. Observations and assessments require sources; label the analytical
step rather than implying that a vendor supports your recommendation.

Use current primary sources for price examples, with region, currency, date,
fee base, included services and comparison limits. A public list price is not a
typical negotiated contract or a provider's retained margin. Leave unsupported
benchmarks absent instead of inventing an industry average.

Market scenarios use annual units × provider revenue per unit for TAM, a
serviceable share for SAM, and an obtainable share **of SAM** for SOM. Define the
boundary, units, geography, base year, horizon, assumptions and exclusions. SOM is
an annual run rate at the horizon, not cumulative revenue. Separate observed demand
from modeled rates/shares, account for overlap, and explain what a proxy omits.
If sizing is not defensible, leave scenarios empty and explain the missing inputs
in `market.summary` and `market.boundary`.

For economics, define numerator, denominator, cohort and period. Record missing
internal inputs explicitly; don't manufacture CAC, LTV, margins or retention.

## Finish

From the data project, run:

```sh
python3 productscapes.py validate <domain-id> --strict-ids
python3 productscapes.py build <domain-id> --sections value-growth start
```

The validator checks source references, customer/job/KPI ownership, product and
competitor IDs, dates, URLs and market-input ranges. Builds render empty states
for older domains without this optional artifact and preserve source JSON.
Check the Business menu, source links, responsive layout and scenario calculator.
Keep any project navigation override consistent with the new section.

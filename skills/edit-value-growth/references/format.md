# Value & Growth format

The authoritative shape is the toolkit's `_config/_schema/value-growth.schema.json`.
All authored prose is plain text, escaped by the renderer. Do not embed HTML.

`schemaVersion: "1.0"`, `domainId`, `status: "draft" | "ready"`, and `title` are
required. A draft may be partial. A ready model also needs `updated`, `summary`,
`scope`, `framework`, at least one `segments` entry, `market`, at least one
`economics` entry and `sources`.

| Field | Purpose |
|---|---|
| `framework` | Summary, strategy definitions (`id`, `name`, `definition`), evidence |
| `entryStrategy` (optional) | Summary, entry-model definitions, dated provider examples through evidence sources, evidence |
| `segments[]` | `id`, `name`, `summary`, model references, outcome, value/pricing units, charging model, proof of value, selling, positioning, activation, evidence |
| `benchmarks[]` | Dated public price examples with `competitorId`, scope and caveats |
| `providers[]` | Competitor perspectives with a summary, labeled explanatory points and evidence |
| `growthLoops[]` | Ordered mechanism steps, linked segment IDs, measurable signals, constraint and evidence |
| `market` | Boundary, context observations, scenarios and exclusions |
| `economics[]` | Metric definition, formula, purpose, measurement cautions, data availability and evidence |
| `constraints[]` | Material constraints, explanations and evidence |
| `sources[]` | Unique `id`, `title`, `publisher`, absolute HTTP(S) `url`, `accessed` date, optional `published` date |

Each segment has `customerRefs: [{customerId, jobIds, kpiIds}]`, `productIds` and
`competitorIds`. Jobs and KPIs must belong to the referenced persona. KPIs use
stable IDs, not names. Empty reference arrays are allowed for prospective segments;
explain their status rather than assigning an unrelated persona.

`selling` contains `motion` (bottom-up/top-down/hybrid), users, champions, buyers,
payers, channels and rationale. `positioning` contains `strategy`
(dominant/differentiated/disruptive/mixed/unclassified), alternative, rationale and
conditions. `activation` contains entry, firstValue, repeatValue, expansion and
frictions. List fields hold arrays of plain text.

Optional `entryStrategy` appears in Activation & growth. It contains `summary`,
`models`, `examples` and `evidence`. Each model has `id`, `name`, `definition`,
`bestFit`, `conversion` and `limits`. Each provider example has `id`,
`competitorId`, `name`, `summary`, `caveat` and `evidence`; use the cited source's
access date and distinguish the software offer from underlying transaction fees.

A segment can add `activation.entryOffer` with `modelIds` referencing those entry
models, plus `rationale`, `freemiumFit`, `trialFit`, `evaluationScope`, `limits`,
`paidTrigger`, `conversionMetric` and `evidence`. When an entry offer is present,
all these fields are required. Define the metric's buyer/account cohort and time
window; label a proposed window separately from observed vendor terms or results.
The additions are optional, so existing models remain valid without them.

Evidence blocks use this shape:

```json
{
  "kind": "inferred",
  "note": "Interpretation of the cited commercial and product evidence.",
  "sourceIds": ["vendor-pricing"]
}
```

Each market scenario has `id`, `name`, `geography`, `baseYear`, `horizonYears`,
three-letter `currency`, `unitLabel`, `revenueLabel`, `units`, `revenuePerUnit`,
`serviceableShare`, `obtainableShare`, assumptions, limitations and evidence.
Shares are fractions from 0 to 1. Units and revenue per unit are finite,
nonnegative numbers. No expression strings are evaluated.

For example, 10,000 eligible accounts × EUR 120 annual provider revenue/account
gives EUR 1.2 million TAM. A serviceable share of 0.4 gives EUR 480,000 SAM; an
obtainable share of 0.1 gives EUR 48,000 SOM. These inputs are illustrative, not
research about any real domain. The renderer calculates outputs rather than
storing redundant totals. Browser edits are exploratory and are not saved.

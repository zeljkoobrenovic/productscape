---
name: edit-customers
description: "Create or edit customer data for a product domain: customer groups, personas, jobs-to-be-done (JTBD), customer journey stories, KPI pyramids, per-customer product strategy, customer insights, and external reference links. Use when adding a customer segment, refining a persona, writing JTBD/journeys, building KPI pyramids, adding sourced insights, or curating external links in _config/product-domains/group/domain/customers/customers.json, insights.json, and links.json. Keeps customer IDs consistent across products, teams, and insights."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Customers

Authoring skill for `customers/customers.json` and `customers/insights.json`. Combines
the customer-modeling methodology with this repo's exact schema, ID wiring, and the
validate→regenerate loop. Read [domain model](../_references/domain-model.md) first.

Target files (per domain):
- `_config/product-domains/<group>/<domain>/customers/customers.json`
- `_config/product-domains/<group>/<domain>/customers/insights.json`
- `_config/product-domains/<group>/<domain>/customers/links.json` (optional — external reference links)
- icons in `customers/icons/`, media in `customers/media/`

**Read the existing files and the customer schema before editing.** Optionally
compare `ride-sharing-marketplace` in productscape-examples for modeling depth.

## Method (what good looks like)

### Segmentation
- List every party in the value exchange: buyers, users, admins, operators,
  partners, beneficiaries, regulators.
- Group by materially different job context, risk, economics, decision process, and
  success criteria — not demographics.
- Each segment must change product strategy or capability priorities; merge any that
  don't. Avoid one generic "user" for multi-sided domains.

### Jobs-to-be-done
- Write jobs as outcome progress ("Book a reliable ride for a time-sensitive trip"),
  never "use feature X".
- Break each into real steps with decisions, frictions, and the streams/capabilities
  that support them.
- `Discovery` = awareness before use; `Evaluation` = the decide-before-trial step.
  Neither is in-product browsing/search.

### Journeys
- **A journey story is the customer's adoption journey WITH THE PRODUCT, not a
  walkthrough of doing their job.** The single most common mistake is writing a
  task-execution narrative (e.g. "prepare tender → run bids → award → publish") —
  that content belongs in JTBD steps or streams, never in journey stages.
- **Stages are fixed — use exactly these six, in this order, as the `stage` values:**
  `Trigger`, `Discovery`, `Evaluation`, `Trial`, `Engagement`, `Retention`.
  - `Trigger` — the pain/event that starts the search (not a work task).
  - `Discovery` — how they become AWARE of the product (referrals, conferences,
    analyst reports, app stores, sales outreach, a colleague's screen) before use.
  - `Evaluation` — deciding before committing: comparisons, references, security/
    procurement review, pricing vs. value, trust and compliance checks.
  - `Trial` — first bounded real use: pilot, parallel run, first booking/load.
  - `Engagement` — the product embedded in their routine; depth and habit.
  - `Retention` — why they stay/renew/expand; advocacy and lock-in moments.
- Litmus test per stage: if the narrative would still be true without this product
  existing, it is a job narrative, not an adoption journey — rewrite it.
- Include trust/compliance/payment moments where material (usually in Evaluation).

### KPI pyramids
- A top customer outcome and (where modeled) business outcome, each decomposed into a
  real pyramid that **fans out at every level**.
- **Shape invariant (enforce this): every non-leaf node has ≥2 children; a leaf has 0.
  Never exactly one child, at any level.** A `top → 1 branch → 1 child → 1 leaf` chain
  is a line, not a pyramid — the single most common mistake here.
- **Target shape:** 4 levels — `top → 2 branches → 2 mid metrics each → 2 diagnostic
  leaves each` (1 + 2 + 4 + 8 = 15 nodes). A 3-level pyramid
  (`top → 2 branches → 2 leaves each`, 7 nodes) is acceptable when a domain genuinely
  has fewer meaningful diagnostics — but still ≥2 children per non-leaf node. Do not
  pad with vanity metrics just to hit the count; every node must be a real,
  decision-relevant measure.
- Each level decomposes the parent: branches are outcome themes, mid metrics are the
  drivers of that theme, leaves are the measurable diagnostics that move the driver.
- Only leaves carry a `unit` + `currentValue` that is a terminal measurement; give
  every metric a `unit` and avoid vanity terminals.
- KPI **ids** must be unique within a customer (across both pyramids). Reuse KPI
  **names** consistently across customers, teams, and insights (they link by name, not
  id) — every `northStar`/`supporting` name must exist as a node in that
  customer's pyramids.

### Insights (evidence)
- Record sourced facts with `sourceIds`; make inference explicit; don't invent
  metrics. Link each insight to the customers/jobs/KPIs it affects.

### External links (further reading)
- Optional `links.json` curates external pages for a reader who wants to probe the
  domain further (product surfaces, industry context, trust/safety, regulators).
- Organize links into named groups; give each link a one-sentence `relevance` that
  says *why this matters to this domain* — not a generic site description.
- Prefer primary/official sources; verify URLs resolve. Omit the file entirely if
  there is nothing worth linking — the Links tab then shows an empty state.

## Exact schema

### customers.json — top level is an **array of groups**

```json
[
  {
    "group": "Riders",
    "customers": [ { /* persona */ } ]
  }
]
```

### persona object

```json
{
  "id": "ridu",                         // lowercase short stable code
  "name": "Urban Time-Sensitive Rider",
  "description": "…",
  "icon": "ridu.png",                   // file in customers/icons/
  "careAbout": ["…"],                   // list of strings
  "winsThem": ["…"],
  "theirFear": ["…"],
  "jobsToBeDone": [ { /* jtbd */ } ],
  "customerJourneyStories": [ { /* journey */ } ],
  "kpiPyramids": { /* see below */ },
  "productStrategy": { "vision": "…", "timeHorizons": { /* 1/3/5 year */ } }
}
```

### jobsToBeDone[] item

```json
{
  "id": "book",
  "name": "Book a reliable ride for a time-sensitive trip",
  "whatItIs": "…",
  "outcome": "…",
  "steps": [
    {
      "step": "Define the trip and compare options",
      "description": "…",
      "streamsNeeded": [
        { "id": "trip", "name": "Trip Request and Intent Capture",
          "howItSupports": "…" }
      ],
      "media": []
    }
  ],
  "media": []
}
```
> `steps[].streamsNeeded[].id` must reference a real stream id in
> `product-stream.json` (or a brick id in `product-bricks.json`). Keep `name` in sync.

### customerJourneyStories[] item

```json
{
  "id": "journey-ridu-airport",
  "name": "Airport ride without pickup friction",
  "linkedJobIds": ["book", "trust"],      // ids from this persona's jobsToBeDone
  "summary": "…",
  "stages": [
    { "stage": "Trigger",    "narrative": "…", "media": [] },
    { "stage": "Discovery",  "narrative": "…", "media": [] },
    { "stage": "Evaluation", "narrative": "…", "media": [] },
    { "stage": "Trial",      "narrative": "…", "media": [] },
    { "stage": "Engagement", "narrative": "…", "media": [] },
    { "stage": "Retention",  "narrative": "…", "media": [] }
  ],
  "media": [ { "type": "image", "src": "…", "title": "…", "alt": "…" } ]
}
```

> The six stages above are the fixed adoption-journey model (see "Journeys").
> Do not invent task-phase stage names like "Preparation", "Tender", or "Award".

### kpiPyramids

Every non-leaf node below has ≥2 children — mirror this fan-out (top → 2 branches →
2 mid metrics each → 2 leaves each). Do NOT emit single-child chains.

```json
{
  "customerOutcomes": {
    "top": { "id": "rrel", "name": "Reliable on-time trip completion",
             "description": "…", "unit": "%", "currentValue": "72.5",
             "link": "…", "linkLabel": "Open KPI dashboard",
             "icon": "kpi-ridu-rrel.png" },
    "branches": [
      { "id": "rspd", "name": "Speed and predictability",
        "currentValue": "72", "link": "…", "linkLabel": "Open KPI dashboard",
        "icon": "kpi-ridu-rspd.png",
        "children": [
          { "id": "reta", "name": "ETA accuracy", "description": "…",
            "unit": "minutes", "currentValue": "58", "icon": "kpi-ridu-reta.png",
            "children": [
              { "id": "rwtm", "name": "Rider wait time", "description": "…",
                "unit": "minutes", "currentValue": "6.9", "icon": "kpi-ridu-rwtm.png",
                "children": [] },
              { "id": "rpup", "name": "Pickup punctuality", "description": "…",
                "unit": "%", "currentValue": "88", "icon": "kpi-ridu-rpup.png",
                "children": [] }
            ] },
          { "id": "rcxl", "name": "Avoidable cancellation rate", "description": "…",
            "unit": "%", "currentValue": "3.1", "icon": "kpi-ridu-rcxl.png",
            "children": [
              { "id": "rrem", "name": "Rematch recovery rate", "description": "…",
                "unit": "%", "currentValue": "75", "icon": "kpi-ridu-rrem.png",
                "children": [] },
              { "id": "rdrv", "name": "Driver no-show rate", "description": "…",
                "unit": "%", "currentValue": "1.4", "icon": "kpi-ridu-rdrv.png",
                "children": [] }
            ] }
        ] }
      // ... a second branch (e.g. "Trust and confidence") with the same 2×2 fan-out
    ]
  }
  // a businessOutcomes pyramid of the same shape may also be present
}
```
> Shape rule: `top → ≥2 branches → ≥2 mid metrics each → ≥2 leaves each`. Every
> non-leaf node has ≥2 children; only leaves have `children: []`. Never one child.

### productStrategy.timeHorizons (per horizon: `year1`, `year3`, `year5`)

```json
{
  "focus": "…",
  "productTheme": "…",
  "customerKPI": { "northStar": "…", "supporting": ["…"] },
  "businessKPI": { "northStar": "…", "revenueStreams": ["…"], "supporting": ["…"] }
}
```
> `northStar`/`supporting` should reuse exact KPI **names** from the pyramids.

### insights.json

```json
{
  "domainId": "<domain>",
  "updated": "YYYY-MM-DD",
  "sources": [
    { "id": "uber-q4-2025", "title": "…", "url": "https://…",
      "publisher": "…", "date": "YYYY-MM-DD" }
  ],
  "items": [
    {
      "id": "rsm-01",                       // domain-prefix + number
      "title": "…", "summary": "…", "implication": "…",
      "priority": "high",                   // high | medium | low
      "tags": ["scale", "frequency"],
      "sourceIds": ["uber-q4-2025"],        // → sources[].id
      "linkedCustomers": [
        { "customerId": "ridu", "jobIds": ["book"],
          "kpiIds": ["rrel"] }  // KPI pyramid node ids (never the legacy name-based `kpis`)
      ]
    }
  ]
}
```

### links.json (optional) — external reference links

```json
{
  "domainId": "<domain>",
  "updated": "YYYY-MM-DD",
  "groups": [
    {
      "group": "Product surfaces",
      "description": "Optional one-line description of the group.",
      "links": [
        {
          "title": "How Uber works — ride options",
          "url": "https://www.uber.com/us/en/ride/how-uber-works/",
          "relevance": "Why this page matters to this domain (one sentence).",
          "tags": ["rider", "product"]          // optional
        }
      ]
    }
  ]
}
```
> Top level is an **object** with `groups[]` (not a bare array). Rendered as the
> **Links** tab in `customers/index.html`. `description` and `tags` are optional;
> `title`, `url`, and `relevance` carry the value. No cross-file ID references.

## Cross-file rules to keep intact

When you add/rename a **persona id**, update references in:
- `product-deployments/products.json` → `portfolio.products[].primaryCustomers[].id`
- `teams/teams.json` → `…teams[].primaryCustomers[].customerId`
- `customers/insights.json` → `items[].linkedCustomers[].customerId`

When you add/rename a **JTBD id**, update `linkedJobIds` in the same persona's
journeys and `jobIds` in insights. When you change a **KPI name**, update teams'
metrics and the persona's `productStrategy` northStar/supporting (insights link by `kpiIds`)
(these link by name). When a JTBD step needs a stream that doesn't exist yet, either
add the stream (`edit-streams`) or point at an existing brick id.

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`
   (validator does not check customer-ID refs — verify those by hand against the
   files above, or run `audit-domain-balance`).
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
   (name/description come from the domain's `start/config.json`). Generator wipes the customers docs
   folder — ensure that area's worktree is clean first.
3. Report personas/insights added or changed and which referencing files you updated.

## Avoid

- A single generic "user" segment in a multi-sided domain.
- JTBD written as feature usage, or `Discovery`/`Evaluation` used for in-product
  search/browse.
- **KPI pyramids that are lines, not pyramids** — any non-leaf node with exactly one
  child (`top → 1 branch → 1 child → 1 leaf`). Every non-leaf node needs ≥2 children.
- Vanity terminal metrics, arbitrary precise targets, or padding leaves just to reach
  a node count.
- `northStar`/`supporting` names (or insight `kpiIds`) that don't exist as a node in the
  customer's pyramids; duplicate KPI ids within a customer.
- Inventing business metrics or sources; copying identical strategy horizons across
  personas.
- Leaving cross-file customer references dangling.

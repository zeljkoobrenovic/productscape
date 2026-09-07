---
name: edit-competition
description: "Create or edit the competitive landscape for a product domain: competitor players, their category, HQ, regions, descriptions, sourced business stats with official URLs, and official links in _config/product-domains/group/domain/business/competition.json. Use when adding a competitor, updating market positioning, or refreshing business metrics. Every business stat must carry an official source URL and reported scope — no invented metrics."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Competition

Authoring skill for `business/competition.json` — the sourced competitive landscape.
Combines competition/market-research methodology with this repo's exact schema. Read
[domain model](../_references/domain-model.md) first, and **read the existing file plus
the competition schema (optionally compare `ride-sharing-marketplace` in productscape-examples) before editing.**

## Method (what good looks like)

- Include players that genuinely compete for the same customers/jobs; state the
  inclusion logic in `scope`. Categorize (global_leader, regional, challenger, niche).
- **Every business stat is sourced.** Use official sources (investor relations, annual
  reports, regulator filings) with a real `sourceUrl` and the reported `period` and
  `scope`. Preserve reported scope — don't normalize away caveats. **Never invent
  metrics or precision.** Omit a stat rather than fabricate it.
- Logos go in `business/logos/`; reference by relative path.

## Exact schema

```json
{
  "generatedOn": "YYYY-MM-DD",
  "domain": "<domain-id>",
  "title": "… Competitive Landscape",
  "scope": { "description": "…", "inclusionLogic": "…", "notes": "…" },
  "players": [
    {
      "id": "uber",                              // lowercase slug, stable
      "logo": "logos/uber.png",
      "name": "Uber",
      "hq": "San Francisco, United States",
      "category": "global_leader",
      "primaryRegions": ["north_america", "europe"],
      "description": "…",
      "businessStats": [
        {
          "metric": "gross_bookings", "value": "$162.8bn",
          "period": "FY2024", "scope": "platform",
          "sourceTitle": "Uber Announces Results for Fourth Quarter and Full Year 2024",
          "sourceUrl": "https://investor.uber.com/…"
        }
      ],
      "links": {
        "website": "https://…", "investor_relations": "https://…",
        "newsroom": "https://…", "blog": "https://…",
        "engineering_blog": "https://…", "linkedin": "https://…"
      }
    }
  ]
}
```

## Cross-file rules

This artifact is reference intelligence — it has no incoming ID dependencies from
other files. The discipline is **sourcing**, not cross-references. Keep `domain` equal
to the domain id, and keep category/region vocabularies consistent with existing
players in the file.

## After editing

1. `python3 productscapes.py validate <domain-id>`
   (JSON validity; competition has no brick/team integrity checks).
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
3. Report players added/changed and confirm every new stat has an official source URL.

## Avoid

- Any business stat without a `sourceUrl` and reported `period`/`scope`.
- Invented or suspiciously precise numbers; normalizing away reported scope caveats.
- Including non-competitors to pad the list.
- Inconsistent category/region vocabularies vs existing players.

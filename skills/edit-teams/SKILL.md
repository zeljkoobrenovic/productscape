---
name: edit-teams
description: "Create or edit the team and org model for a product domain: org design, team groups, individual teams, team types (stream-aligned/platform/enabling/complicated-subsystem/other), team descriptions, customer/stream/brick/team dependencies, and headcount in _config/product-domains/group/domain/teams/teams.json. Use when adding a team, restructuring org groups, wiring brick/customer dependencies, or sizing teams. Keeps team IDs consistent with brick ownership and data-asset ownership."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Teams

Authoring skill for `teams/teams.json` — the organizational design. Combines team
topology methodology with this repo's exact schema and the validate→regenerate loop.
Read [domain model](../_references/domain-model.md) first, and **read the existing file
plus the team schema (optionally compare `maas` in productscape-examples) before editing.**

## Method (what good looks like)

- Use **team topology types**: `stream-aligned` (owns a customer/value stream),
  `platform` (provides internal products/capabilities), `enabling` (uplifts other
  teams), `complicated-subsystem` (deep specialist area), `other` (temporary or
  cross-functional).
- Each team has a clear `description` (its mission), depends on a coherent set of
  **bricks**, serves **customers**, supports the **streams** it delivers, and depends
  on a small number of other teams. Avoid teams with no distinct mission or no brick
  dependencies.
- Group teams into **groups** with a `groupDirectHeadcount` for lightweight group
  leadership. Keep brick ownership unambiguous: each brick should be the primary
  responsibility of exactly one team.
- Headcount is realistic per team (typically 8–11 FTE) plus a small group-direct
  headcount for leadership.

## Exact schema

```json
{
  "orgDesign": {
    "domainId": "…", "domainName": "…", "companyProfile": "…", "operatingModel": "…",
    "teamTypes": [
      { "id": "stream-aligned", "name": "Stream-aligned", "color": "#2563eb", "description": "…" },
      { "id": "platform",       "name": "Platform",        "color": "#0891b2", "description": "…" },
      { "id": "enabling",       "name": "Enabling",        "color": "#16a34a", "description": "…" },
      { "id": "complicated-subsystem", "name": "Complicated subsystem", "color": "#9333ea", "description": "…" },
      { "id": "other",          "name": "Other",           "color": "#6b7280", "description": "…" }
    ],
    "teamDependencyTypes": [
      { "id": "collaboration",  "name": "Collaboration",   "description": "Working closely together with another team." },
      { "id": "x-as-a-service", "name": "X-as-a-Service",   "description": "Consuming or providing something with minimal collaboration." },
      { "id": "facilitating",   "name": "Facilitating",     "description": "Helping (or being helped by) another team to clear impediments." },
      { "id": "other",          "name": "Other",            "description": "Any other type of dependency not covered above." }
    ]
  },
  "groups": [
    {
      "id": "pkcg", "name": "Parking and Curb Operations", "mission": "…",
      "groupDirectHeadcount": {
        "headcount": 4,
        "description": "Provide cross-team direction, portfolio tradeoffs, architecture coherence, and talent quality across this group."
      },
      "groups": [],                          // groups may nest
      "teams": [ { /* team */ } ]
    }
  ]
}
```

### team object (canonical shape — the only shape used in the repo)

```json
{
  "id": "pkor",                              // lowercase slug, unique across all teams
  "name": "Parking Core",
  "type": "stream-aligned",                  // → orgDesign.teamTypes[].id
  "description": "Own zone configuration, tariff logic, session control, and asset monetization workflows.",
  "teamHeadcount": { "headcount": 9, "description": "Cross-functional product team." },
  "documentLinks": [],
  "customerDependencies": [
    { "customerId": "mpdu", "description": "" }   // customerId → customers.json persona id
  ],
  "streamDependencies": [
    { "streamId": "driver-or-citizen-find-the-right-parking-option", "description": "" }  // → product-stream.json
  ],
  "brickDependencies": [
    { "brickId": "dypr", "description": "" }       // → product-bricks.json brick id
  ],
  "otherTeamDependencies": [
    { "teamId": "stld", "type": "facilitating", "description": "" }   // type → orgDesign.teamDependencyTypes[].id
  ]
}
```

## Cross-file rules to keep intact

- `brickDependencies[].brickId` → real brick ids in `product-bricks.json`. Treat the
  brick a team is built around as its owned brick; every brick should be the primary
  responsibility of exactly one team. Flag unowned bricks and double-owned bricks.
- `customerDependencies[].customerId` → persona ids in `customers/customers.json`.
- `streamDependencies[].streamId` → stream ids in `product-bricks/product-stream.json`.
- `otherTeamDependencies[].teamId` → real team ids (no dangling refs);
  `otherTeamDependencies[].type` → an id in `orgDesign.teamDependencyTypes`.
- `type` → an id in `orgDesign.teamTypes`. `teamTypes`/`teamDependencyTypes` normally
  come from the shared model `_config/_shared/team-model.json` — omit them in domain
  files unless the domain genuinely diverges (a local value overrides the shared one).
- `data/data-assets.json` `ownerTeamId`/`stewardTeamIds` should point back at real
  team ids — wiring ownership both ways improves traceability.

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`
   (checks team uniqueness, headcount, team types, and brick/customer/stream/team
   deps; verify brick-ownership coverage with `audit-domain-balance`).
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
3. Report teams added or changed, brick ownership assigned, and dependencies wired.

## Avoid

- Bricks depended on by zero or many teams with no clear owner.
- Teams with no brick dependencies or no distinct mission.
- Dangling team/brick/customer/stream references.
- `type` or dependency `type` values not declared in `orgDesign`.
- Arbitrary headcounts unmoored from the team's scope.

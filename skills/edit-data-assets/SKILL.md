---
name: edit-data-assets
description: "Create or edit data assets for a product domain: logical data objects, their classification, personal-data level, legal tags, security criticality, governance (retention/residency/sharing), backing stores, interfaces, and team ownership in _config/product-domains/group/domain/data/data-assets.json. Use when adding a data asset, setting data governance/classification, defining stores, or wiring asset ownership and derivations. Keeps asset IDs consistent with product-brick dataDependencies."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Data Assets

Authoring skill for `data/data-assets.json` — the domain's data catalog. Read
[domain model](../_references/domain-model.md) first, and **read the existing file plus
the data-asset schema (optionally compare `ride-sharing-marketplace` in productscape-examples) before editing.**

## Method (what good looks like)

- A **data asset** is a logical data object (Customer Profile, Trip Ledger), not a
  physical table — physical stores live in the `stores` catalog and are referenced.
- Capture **governance reality**: classification, personal-data level, legal tags,
  security criticality, retention, residency, sharing — where the domain actually has
  obligations. Don't invent regulatory tags.
- Each asset has an **owning team** and is used by bricks via `dataDependencies`. An
  asset no brick uses and no team owns is likely noise.

## Exact schema

```json
{
  "metadata": { "title": "…", "description": "…", "modelVersion": "…" },
  "rootGroups": [
    {
      "name": "People, Accounts, and Access Data",   // groups use name, not id
      "description": "…",
      "subGroups": [ { "name": "…", "description": "…", "assets": [ … ] } ]
    }
  ],
  "stores": [
    { "id": "customer-profile-db", "name": "Customer Profile DB",
      "kind": "operational-database", "description": "…",
      "technology": "…", "status": "active", "classification": "restricted" }
  ]
}
```

### asset object

```json
{
  "id": "customer-profile",                  // hyphenated slug, lowercase, stable
  "name": "Customer Profile",
  "kind": "logical-object",
  "description": "…",
  "classification": "restricted",            // e.g. public | internal | confidential | restricted
  "personalDataLevel": "personal",           // e.g. none | personal | sensitive
  "dataSubjects": ["customer"],
  "legalTags": ["gdpr"],
  "securityCriticality": "high",
  "accessScope": "…",
  "businessMeaning": "…",
  "status": "active",
  "stores": [ { "storeId": "customer-profile-db", "role": "system-of-record" } ], // → stores[].id
  "interfaces": [ { "type": "api", "name": "customer-profile api", "description": "…" } ],
  "ownerTeamId": "",                          // → teams.json team id (fill it in)
  "stewardTeamIds": [],                       // → teams.json team ids
  "derivedFromAssetIds": [],                  // → other asset ids in this file
  "governance": { "retention": "…", "residency": "eu", "sharingPolicy": "…" }
}
```
> Match the enum-like values (classification, personalDataLevel, kind, status) to what
> existing assets in the domain already use — don't introduce parallel vocabularies.

## Cross-file rules to keep intact

- An asset `id` is referenced by `product-bricks.json` →
  `bricks[].dataDependencies[].assetId`. When you add/rename an asset, update every
  referencing brick (and consider whether a brick should own/read it).
- `stores[].storeId` on an asset → an entry in the top-level `stores` array.
- `ownerTeamId` / `stewardTeamIds` → real team ids in `teams/teams.json`. The
  reference domain often leaves `ownerTeamId` empty — filling it improves traceability
  (and `audit-domain-balance` flags empties).
- `derivedFromAssetIds` → other asset ids in this file.

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`
   (does not check assetId↔brick wiring — verify by hand or with `audit-domain-balance`).
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
   (the bricks generator builds data-asset pages).
3. Report assets/stores added or changed and the brick/team references touched.

## Avoid

- Modeling physical tables as assets (use `stores`).
- Inventing legal/governance tags the domain has no basis for.
- Orphan assets (no brick uses them, no team owns them).
- Introducing new classification/kind vocabularies inconsistent with existing assets.

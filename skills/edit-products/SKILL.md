---
name: edit-products
description: "Create or edit products and the deployment model for a product domain: the product portfolio (id, name, type, primary customers) and the deployment.json channel groups, sub-channels, and deployed bricks with the products that use them. Use when adding a product, wiring products to customers, or editing runtime/app-store/dashboard channels and deployed bricks in _config/product-domains/group/domain/product-deployments/."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Products & Deployment

Authoring skill for `product-deployments/products.json` and `deployment.json`.
Combines delivery/business-model methodology with this repo's exact schema and the
validate→regenerate loop. Read [domain model](../_references/domain-model.md) first, and
**read the existing files and the products/deployment schemas before editing.**
Optionally compare `maas` in productscape-examples for modeling depth.

## Method (what good looks like)

- A **product** is a customer-facing offering with its own type and customers. Products
  are composed from bricks; the brick→product wiring lives in `deployment.json`
  (`deployedBricks[].usedInProducts`), not inside the product.
- `deployment.json` is the menu of runtime/app-store/dashboard channels and the bricks
  deployed to each. Each deployed brick records which products use it.
- Every product traces to ≥1 primary customer. Every brick that a product depends on
  should appear in `deployment.json` with that product listed in its `usedInProducts`.
- Keep it lean: no per-product interface catalogs, needed-brick blocks, or environment
  lists — that detail is not part of this schema.

## Exact schema — products.json

```json
{
  "portfolio": {
    "name": "Arrive Mobility Platform Portfolio",
    "version": "1.0",
    "products": [
      {
        "id": "pkop",                       // lowercase short stable code
        "name": "Parking and Curb Operations Platform",
        "icon": "mpdu.png",
        "type": "B2B / B2G Operations",
        "primaryCustomers": [
          { "id": "mpdu", "name": "Municipal Parking Director" }   // → customers.json persona id
        ]
      }
    ],
    "deploymentModelRef": "deployment.json"
  }
}
```

## Exact schema — deployment.json

```json
{
  "metadata": { "title": "…", "description": "…", "modelVersion": "4.0" },
  "channels": [
    {
      "groupId": "public-cloud", "groupName": "Public Cloud",
      "groupType": "runtime", "description": "…",
      "channels": [
        {
          "subChannelId": "public-cloud-parking-and-curb-control",
          "subChannelName": "Parking and Curb Control Account",
          "channelType": "public-cloud", "description": "…",
          "deployedBricks": [
            {
              "brickId": "pcon",                       // → product-bricks.json brick id
              "brickName": "Parking Configuration & Policy Management",
              "deploymentRole": "Backend service, worker, and data package deployed to the public cloud runtime.",
              "usedInProducts": [
                { "productId": "pkop", "description": "Controls the operating model for tariffs, zones, permits, and exemptions." }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

> `groupType` is typically `runtime` (public cloud) or `distribution` (mobile app
> stores). Full-stack bricks are commonly deployed to both the cloud runtime and the
> iOS/Android app-store sub-channels.

## Cross-file rules to keep intact

- `primaryCustomers[].id` → real persona id in `customers/customers.json` (keep `name` in sync).
- `deployedBricks[].brickId` → real brick id in `product-bricks.json` (keep `brickName`
  in sync). Deploying a brick that doesn't exist? Create it with `edit-product-bricks` first.
- `deployedBricks[].usedInProducts[].productId` → a product `id` in `products.json`.
- `portfolio.deploymentModelRef` should be `"deployment.json"`.

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`
   (validator checks JSON + IDs; verify customer/brick/product back-references by hand
   or with `audit-domain-balance`).
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
3. Report products/channels added or changed and the references you wired.

## Avoid

- A deployed brick that references a product or brick that doesn't exist.
- Duplicating brick definitions inside products (products reference bricks).
- Re-introducing legacy fields (`interfaces`, `neededBricks`, `environments`,
  `deploymentChannelRef`, per-product `deploymentModelRef`) — they are not part of this schema.
- Inventing customers or bricks just to populate fields.

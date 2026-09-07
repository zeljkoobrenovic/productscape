---
name: edit-streams
description: "Create or edit product streams for a product domain: outcome-based streams, their outcomes, brick dependencies, and end-to-end flows with steps, key facts, pain points, and step-level dependencies in _config/product-domains/group/domain/product-bricks/product-stream.json. Use when adding a stream, modeling a customer/operator journey as a flow, or wiring stream and step dependencies to product bricks. Keeps stream IDs consistent with JTBD streamsNeeded."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# Edit Streams

Authoring skill for `product-bricks/product-stream.json`. Streams are the
outcome-oriented, cross-brick journeys that sit above bricks. Read
[domain model](../_references/domain-model.md) first, and **read the existing file plus
the relevant toolkit schema (optionally compare `ride-sharing-marketplace` in productscape-examples) before editing.**

## Method (what good looks like)

- A **stream** is an outcome-based journey ("Book and Complete a Reliable Trip") that
  composes multiple bricks, not a single capability. Streams are durable and
  customer/operator-meaningful.
- Each stream names concrete **outcomes**, the **bricks** it depends on, and one or
  more **flows** broken into real steps with decisions, key facts, and pain points.
- Streams are the bridge between customer JTBD (`customers.json` →
  `jobsToBeDone[].steps[].streamsNeeded[].id`) and bricks. Keep stream IDs stable.

## Exact schema

```json
{
  "metadata": { "title": "…", "description": "…", "definitions": { … },
                "sources": [ … ], "flowModelVersion": "…", "flowModelNote": "…" },
  "rootGroups": [
    {
      "name": "Rider Journeys",                 // groups use name, not id
      "description": "…",
      "subGroups": [ { "name": "…", "streams": [ … ] } ],
      "streams": [ … ]                          // streams may sit on a group directly too
    }
  ]
}
```

### stream object

```json
{
  "id": "rider-book-and-complete-a-reliable-trip",   // hyphenated slug, lowercase
  "name": "Book and Complete a Reliable Trip",
  "type": "outcome-based-stream",
  "description": "…",
  "outcomes": ["Higher trip conversion", "Better repeat rider retention"],
  "brickDependencies": [ { "targetBrickId": "etar", "type": "composition" } ],
  "links": [                                  // grouped; rendered in the Links tab
    { "group": "Evidence", "description": "…",
      "links": [ { "label": "Evidence Explorer",
                   "link": "../../../../evidence-explorer/index.html",
                   "description": "…",
                   "embedLink": "../../../../evidence-explorer/index.html?embed=1",  // optional: renders an iframe
                   "embedHeight": 400 } ] }    // optional; iframe height in px, default 400
  ],
  "flows": [
    {
      "id": "…", "title": "…", "description": "…",
      "steps": [
        {
          "id": "enter-trip-request", "title": "Enter trip request",
          "keyFacts": ["…"], "painPoints": ["…"],
          "dependencies": [
            { "type": "brick", "id": "etar",
              "name": "ETA, Maps and Routing Intelligence",
              "description": "…", "how": "…" }       // id → product-bricks.json brick id
          ]
        }
      ]
    }
  ],
  "externalSystemsThisStreamDependsOn": [],
  "icon": "rider-book-and-complete-a-reliable-trip.png"
}
```

## Cross-file rules to keep intact

- `brickDependencies[].targetBrickId` and flow `steps[].dependencies[].id` (type
  `brick`) → real brick ids in `product-bricks.json`.
- A stream id is referenced by `customers.json`
  (`jobsToBeDone[].steps[].streamsNeeded[].id`) and by
  When you rename a stream id,
  update both.

## After editing

1. `python3 productscapes.py validate <domain-id> --strict-ids`.
2. Regenerate: from the project root,
   `python3 productscapes.py build <domain-id>
   (the bricks generator also builds stream pages).
3. Report streams/flows added or changed and the brick links wired.

## Avoid

- A "stream" that is really a single brick or a UI task.
- Step dependencies pointing at non-existent bricks.
- Renaming a stream id without updating JTBD `streamsNeeded`.
- Flows with no steps, or steps with no key facts / pain points / dependencies.

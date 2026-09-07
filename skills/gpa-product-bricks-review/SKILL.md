---
name: gpa-product-bricks-review
description: "Use in the Productscape project when reviewing `_config/product-domains/**` product bricks, product streams, data assets, layered modules, dependencies, external systems, team ownership, and implementation traceability before editing the model; save the review in the domain root `REVIEW.md`."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# GPA Product Bricks Review

## Purpose

Review the implementation-facing product architecture of a Productscape domain. The goal is to find gaps in product bricks, streams, modules, dependencies, data assets, and ownership in `_config/product-domains/<group>/<domain>/REVIEW.md` so a later editing pass can improve `_config/product-domains/<group>/<domain>/product-bricks/` and related source files.

Resolve the domain ID with `_wiring/domain_paths.py` to find its current group. Group names can change; keep reviews in the resolved domain folder.

## Source Files

Read these files before reviewing:

- `_config/product-domains/<group>/<domain>/product-bricks/product-bricks.json`.
- `_config/product-domains/<group>/<domain>/product-bricks/product-stream.json`.
- `_config/product-domains/<group>/<domain>/data/data-assets.json`.
- `_config/product-domains/<group>/<domain>/teams/teams.json`.
- `_config/product-domains/<group>/<domain>/customers/customers.json`.
- `_config/product-domains/<group>/<domain>/customers/insights.json` when present.
- `_config/product-domains/<group>/<domain>/customers/links.json` when present.
- `_config/product-domains/<group>/<domain>/product-deployments/*.json`.

Run `scripts/validate-domain-model.py <domain>` when useful to catch deterministic reference issues, then continue with qualitative architecture review.

Do not review product-brick or stream `*-evidence.json` files in this skill. Keep traceability review to the source model links among customers, product deployments, product streams, product bricks, data assets, and teams.

## Workflow

1. Build an inventory of root groups, subgroups, bricks, streams, modules, data assets, external systems, and owning teams.
2. Check whether the brick taxonomy reflects durable product and platform capabilities rather than screens, epics, or implementation tasks.
3. Trace important customer jobs and product streams to the bricks, modules, data assets, teams, and external systems needed to deliver them.
4. Review data ownership and dependency realism, especially for regulated, financial, safety, marketplace, identity, analytics, and operational data.
5. Return edit-ready findings with affected IDs and suggested modeling direction.
6. Write the review to `_config/product-domains/<group>/<domain>/REVIEW.md` under a `## Product Bricks Review` section.

## Review Storage

- Create `_config/product-domains/<group>/<domain>/REVIEW.md` if it does not exist.
- If the file exists, update only the `## Product Bricks Review` section and preserve other sections, especially `## Product Domain Review` and `## Teams Review`.
- If the file has no title, add `# <domain-id> Review` at the top.
- Include an `Updated: YYYY-MM-DD` line inside the `## Product Bricks Review` section.
- Treat `REVIEW.md` as a review artifact in the domain root. Do not edit other domain source files during a review-only task unless the user explicitly asks for fixes.

## Review Dimensions

### Product-Brick Shape

- Verify a meaningful three-level structure: root group, subgroup, brick.
- Check that mature domains have enough bricks to be implementation-realistic without becoming a task list.
- Flag vague aspirational bricks, tiny feature tickets, duplicated bricks, and bricks whose boundaries cross unrelated capabilities.
- Review names for product/platform clarity and domain language, not internal project jargon.
- Check statuses and types for plausible investment posture.

### Layered Module Model

- Confirm modules live under `layers` and use supported layer and module type conventions.
- Review whether module choices reflect real architecture: UI, BFF/API, worker, stateless orchestration, stateful/domain service, and integrations.
- Flag bricks with only UI and no service/API where durable behavior is implied, or service-only bricks that should expose interfaces.
- Check `module-` IDs, module descriptions, and intra-brick module dependencies for clarity and stability.
- Confirm legacy fields such as top-level `interfaces`, `internalModules`, or dependency `interface` are not used.

### Dependencies And External Systems

- Review `brickDependencies` for real runtime, data, event, policy, or operational dependencies.
- Check that `sourceModuleId` and target `moduleId` point to plausible modules, not arbitrary placeholders.
- Flag missing dependencies where customer flows clearly require identity, payments, search, messaging, risk, content, pricing, analytics, support, or compliance capabilities.
- Check external systems for explicit interface, dependency reason, and module-level connection.
- Avoid over-modeling every possible relationship; focus on dependencies that shape ownership, delivery, reliability, or risk.

### Product Streams

- Verify streams are outcome-based customer or business flows, not just groups of bricks.
- Check that each stream has realistic outcomes, flow steps, pain points or key facts where the schema supports them, and dependencies that explain how value is delivered.
- Trace stream brick dependencies back to existing product-brick IDs.
- Look for important customer jobs without a stream, streams with no customer or KPI relevance, and steps that skip operational reality.
- Confirm external-system dependencies are used where value delivery crosses company or platform boundaries.

### Data Assets

- Review `data/data-assets.json` as part of the architecture, not as an appendix.
- Check each critical business object has business meaning, classification, personal-data level, data subjects, stores, interfaces, governance, owner team, and system-of-record brick where applicable.
- Confirm product-brick `dataDependencies` use `assetId` and `moduleIds`, not legacy store references.
- Flag sensitive assets without governance, assets without owner/steward, assets not connected to modules, or modules that imply data ownership without data assets.
- Check derived assets and analytics data do not blur operational system-of-record ownership.

### Traceability

- Trace strategic insights and customer jobs to streams and bricks.
- Use `customers/links.json` as domain context when it helps judge whether streams and bricks reflect real product surfaces, market mechanics, or partner ecosystems.
- Trace bricks to owning teams and delivery/product-deployment surfaces.
- Identify architecture claims that need clearer modeling, especially scale, reliability, payment, compliance, safety, marketplace, or AI/ML claims.

### Balance And Pragmatism

- Check whether the model is buildable by real teams and understandable from generated static pages.
- Flag over-abstracted platform layers that hide customer value and over-productized UI flows that ignore service/data reality.
- Look for missing operational capabilities such as observability, admin tooling, support recovery, fraud/risk, incident handling, entitlement, audit, partner onboarding, or data quality where the domain needs them.
- Prefer fixes that clarify ownership and traceability over wholesale taxonomy replacement.

## Output Format

Write the review to `_config/product-domains/<group>/<domain>/REVIEW.md`:

1. `Architecture assessment`: 3-6 bullets on brick realism, stream coherence, data quality, and implementation readiness.
2. `Critical findings`: issues that block reliable editing, generation, or coherent architecture.
3. `Model-quality findings`: missing, vague, duplicated, overloaded, or poorly related bricks/streams/data assets.
4. `Traceability findings`: broken or weak links to customers, teams, product deployments, streams, or data.
5. `Edit backlog`: concrete source changes with file paths, IDs, and expected improvement.

For each finding, include severity, source path and ID, why it matters, and suggested direction for a later editing pass.

## Quality Bar

- Feedback respects the current schema and generator expectations.
- Findings combine implementation realism with customer and business traceability.
- The review identifies both missing capabilities and excessive/unhelpful decomposition.
- Recommendations are scoped enough to edit without re-reviewing the whole domain.

## Avoid

- Reviewing only whether JSON parses.
- Treating product bricks as a generic microservice inventory.
- Asking for more bricks when the real problem is poor boundaries or traceability.
- Editing domain source files other than `REVIEW.md` during a review-only task.

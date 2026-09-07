---
name: gpa-teams-review
description: "Use in the Productscape project when reviewing `_config/product-domains/**/teams/teams.json` for organizational realism, ownership coverage, topology, headcount, dependencies, AI-agent boundaries, and alignment with product bricks, customers, streams, product deployments, and data assets; save the review in the domain root `REVIEW.md`."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# GPA Teams Review

## Purpose

Review the operating model for a Productscape product domain. The goal is to identify ownership gaps, unrealistic team design, staffing imbalance, weak charters, and broken cross-model relationships in `_config/product-domains/<group>/<domain>/REVIEW.md` before an editing pass changes `_config/product-domains/<group>/<domain>/teams/teams.json`.

Resolve the domain ID with `_wiring/domain_paths.py` to find its current group. Group names can change; keep reviews in the resolved domain folder.

## Source Files

Read these files before forming conclusions:

- `_config/product-domains/<group>/<domain>/teams/teams.json`.
- `_config/product-domains/<group>/<domain>/product-bricks/product-bricks.json`.
- `_config/product-domains/<group>/<domain>/product-bricks/product-stream.json`.
- `_config/product-domains/<group>/<domain>/customers/customers.json`.
- `_config/product-domains/<group>/<domain>/customers/insights.json` when present.
- `_config/product-domains/<group>/<domain>/customers/links.json` when present.
- `_config/product-domains/<group>/<domain>/product-deployments/*.json` when present.
- `_config/product-domains/<group>/<domain>/data/data-assets.json` when team ownership or stewardship is modeled.

Use `scripts/validate-domain-model.py <domain>` for deterministic reference checks when useful, but do not limit the review to validator output.

Do not review product-brick or stream `*-evidence.json` files in this skill.

## Workflow

1. Summarize the intended operating model from `orgDesign` (companyProfile, operatingModel, teamTypes), groups, and team descriptions.
2. Build a quick ownership map from product bricks to primary owning teams, supporting teams, and dependencies.
3. Cross-check team missions against customer groups, KPIs, streams, product deployments, data assets, and strategy priorities.
4. Review team topology and staffing for realism: a team should be able to own, evolve, and operate its surfaces.
5. Produce edit-ready feedback without changing source files except `REVIEW.md` unless explicitly asked.
6. Write the review to `_config/product-domains/<group>/<domain>/REVIEW.md` under a `## Teams Review` section.

## Review Storage

- Create `_config/product-domains/<group>/<domain>/REVIEW.md` if it does not exist.
- If the file exists, update only the `## Teams Review` section and preserve other sections, especially `## Product Domain Review` and `## Product Bricks Review`.
- If the file has no title, add `# <domain-id> Review` at the top.
- Include an `Updated: YYYY-MM-DD` line inside the `## Teams Review` section.
- Treat `REVIEW.md` as a review artifact in the domain root. Do not edit other domain source files during a review-only task unless the user explicitly asks for fixes.

## Review Dimensions

### Operating Model Fit

- Check whether top-level groups map to durable value streams, platform foundations, enabling capabilities, data/control functions, or trust/compliance responsibilities.
- Flag groups that mirror a component taxonomy instead of an accountable product or platform operating model.
- Look for missing control functions in regulated, financial, safety-critical, marketplace, data-heavy, or operationally intensive domains.
- Check whether leadership roles are lightweight and coherence-focused rather than a heavy program layer.

### Team Topology

- Verify team types fit the work: stream-aligned for customer/product flows, platform for shared foundations, enabling for specialized improvement, complicated-subsystem for deep technical ownership where justified.
- Challenge teams split purely by frontend/backend when end-to-end product ownership would be more realistic.
- Flag teams that own unrelated surfaces, too many critical bricks, or only a tiny fragment of a user journey.
- Look for missing platform, reliability, data, trust, compliance, or operational-control teams where domain complexity requires them.

### Product-Brick Ownership

- Confirm every product brick has one clear primary owning team unless the local schema explicitly supports shared ownership.
- Check supporting product bricks and dependencies for real recurring collaboration, not vague alignment.
- Identify duplicate ownership, orphaned bricks, teams with no meaningful owned bricks, and bricks owned by teams whose mission does not match the brick.
- Review ownership boundaries across streams so customer journeys do not require excessive handoffs.

### Customer, KPI, And Strategy Alignment

- Check `customerDependencies` and `streamDependencies` against `customers/customers.json` and `product-bricks/product-stream.json`.
- Verify each team `description` explains how the team improves customer or business outcomes, not just how it maintains components.
- Use `customers/links.json` as supporting domain context when assessing whether team responsibilities reflect real customer, partner, market, trust, or operational surfaces.
- Look for strategy horizons or high-priority insights with no accountable team.
- Check whether teams that own critical customer moments also own the metrics and interfaces needed to improve them.

### Dependencies

- Review `otherTeamDependencies` (with `type` ∈ `orgDesign.teamDependencyTypes`),
  `brickDependencies`, `customerDependencies`, and `streamDependencies` for concrete
  operational meaning.
- Flag circular dependencies only when they imply unclear ownership or decision deadlock.
- Check whether team-to-team dependencies reflect real recurring collaboration, x-as-a-service consumption, or facilitation — not vague alignment.
- Prefer explicit dependencies over hidden assumptions, but avoid dependency lists that include every adjacent team.

### Headcount And Sizing

- Review `teamHeadcount.headcount` per team and `groupDirectHeadcount` per group for realism.
- Review team size against mission complexity, on-call burden, domain expertise, design needs, data needs, quality expectations, and regulatory or operational load (typical delivery team 8–11 FTE).
- Flag teams below minimum viable ownership or above realistic coordination size.
- Look for copy-pasted headcounts that ignore domain-specific needs such as data science, partner operations, risk, support tooling, SRE, compliance, or finance operations.

### AI-Agent Boundaries

- If AI agents are modeled, keep them software-delivery assistants only: backend, frontend, QA automation, code review, change risk, test planning, or developer workflow support.
- Flag customer-facing, pricing, trust, marketplace, marketing, or operational decision agents inside team org design unless the user has explicitly asked for that modeling and governance.
- Check that AI-agent use remains bounded by human review, testing, approvals, and production-change controls.

## Output Format

Write the review to `_config/product-domains/<group>/<domain>/REVIEW.md`:

1. `Operating-model assessment`: 3-6 bullets on realism, clarity, and biggest risks.
2. `Ownership findings`: orphaned, overloaded, duplicated, or poorly matched ownership.
3. `Topology and staffing findings`: team shape, size, role, and dependency issues.
4. `Strategy alignment findings`: missing customer, KPI, stream, data, or product-deployment accountability.
5. `Edit backlog`: concrete changes a later editing pass should make, with source file paths and IDs.

For each finding, include severity, affected team or group ID, source path, why it matters, and suggested direction.

## Quality Bar

- The review explains whether a real organization could operate the modeled product.
- Findings connect org design to customer value and product-brick ownership.
- Recommendations are pragmatic: split, merge, rename, restaff, clarify, or reassign only where the model would materially improve.
- Good existing ownership is preserved and named when useful.

## Avoid

- Treating the validator as a substitute for organizational judgment.
- Creating a generic team template unrelated to the domain.
- Suggesting perfect symmetry across groups when the domain needs asymmetry.
- Rewriting teams during a review-only task; only `REVIEW.md` should change.

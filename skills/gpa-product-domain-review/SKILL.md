---
name: gpa-product-domain-review
description: "Use in the Productscape project when reviewing `_config/product-domains/**` customer, JTBD, journey, value proposition, KPI, strategy, insights, research evidence, and competition quality before editing or regenerating domain docs; save the review in the domain root `REVIEW.md`."
---

Read [workspace paths](../_references/workspace.md) when using this skill in a separate data repository.

# GPA Product Domain Review

## Purpose

Review the strategic and customer-facing quality of a Productscape product domain. The goal is not to rewrite the domain during the review; it is to produce specific, grounded feedback in `_config/product-domains/<group>/<domain>/REVIEW.md` that a later editing skill can use to improve the domain safely.

Resolve the domain ID with `_wiring/domain_paths.py` to find its current group. Group names can change; keep reviews in the resolved domain folder.

## Source Files

Read the source model first:

- `_config/product-domains/<group>/<domain>/_domain/DOMAIN.md` when present.
- `_config/product-domains/<group>/<domain>/customers/customers.json`.
- `_config/product-domains/<group>/<domain>/customers/insights.json` when present.
- `_config/product-domains/<group>/<domain>/customers/links.json` when present.
- `_config/product-domains/<group>/<domain>/business/competition.json` when present.
- `_config/product-domains/<group>/<domain>/product-bricks/product-stream.json`.
- `_config/product-domains/<group>/<domain>/product-bricks/product-bricks.json`.
- `_config/product-domains/<group>/<domain>/product-deployments/*.json`.

Treat generated `docs/**` as reference output only. Do not patch generated files during a review.

Do not review product-brick or stream `*-evidence.json` files in this skill. Research/source evidence inside `customers/insights.json` and curated customer-domain links inside `customers/links.json` are in scope.

## Workflow

1. Identify the modeled business, primary customers, and strategic thesis from the domain brief and customer model.
2. Map customer groups to personas, jobs, journeys, KPIs, insights, competition pressures, product deployments, product streams, and teams.
3. Check realism, specificity, and balance before checking syntax. A syntactically valid model can still be strategically weak.
4. Separate findings into defects, gaps, weak assumptions, and improvement opportunities.
5. Include exact source-file references and enough context for an editor to fix the issue without rediscovering it.
6. Write the review to `_config/product-domains/<group>/<domain>/REVIEW.md` under a `## Product Domain Review` section.

## Review Storage

- Create `_config/product-domains/<group>/<domain>/REVIEW.md` if it does not exist.
- If the file exists, update only the `## Product Domain Review` section and preserve other sections, especially `## Teams Review` and `## Product Bricks Review`.
- If the file has no title, add `# <domain-id> Review` at the top.
- Include an `Updated: YYYY-MM-DD` line inside the `## Product Domain Review` section.
- Treat `REVIEW.md` as a review artifact in the domain root. Do not edit other domain source files during a review-only task unless the user explicitly asks for fixes.

## Review Dimensions

### Customer Segmentation

- Verify customer groups are materially distinct by role, need, buying power, operating context, or risk profile.
- Look for missing sides of the market: buyers, end users, operators, partners, regulators, beneficiaries, admins, and internal operations.
- Challenge segments that are just channel labels, generic demographics, or near-duplicates.
- Check whether each major customer has clear pains, decision criteria, care-abouts, fears, and reasons to choose the product.

### Jobs To Be Done And Journeys

- Review jobs as customer progress, not feature usage.
- Confirm job steps reflect real work, choices, constraints, evidence needs, and handoffs.
- Check that `Discovery` means pre-use awareness and `Evaluation` means pre-trial choice, not in-product search or task execution.
- Look for one-step jobs, generic pains, missing recovery paths, missing partner/operator jobs, and weak links to streams or capabilities.
- Confirm job outcomes are observable and map naturally to KPIs.

### Strategy, Value Proposition, And Horizons

- Check whether the strategy says where to win, for whom, and why now.
- Review 1-year, 3-year, and 5-year horizons for plausible sequencing, investment tradeoffs, and increasing ambition.
- Look for horizons that repeat the same theme, promise too much, or skip foundational capabilities.
- Check whether value propositions differentiate against realistic alternatives, not just generic benefits.

### KPI Architecture

- Verify KPIs are specific, measurable, and relevant to the customer or business outcome.
- Challenge invented precision, impossible targets, vanity metrics, and trees with many one-child branches.
- Check for a healthy mix of north-star, leading, lagging, diagnostic, guardrail, customer, operational, and business metrics.
- Confirm KPIs connect to jobs, insights, strategy horizons, product streams, and teams where those references exist.

### Insights And Research Evidence

- Validate that insights are actual implications from research/source material, not restated product decisions.
- Check every insight source ID resolves to `customers/insights.json.sources`.
- Distinguish sourced facts from assumptions and inferences.
- Look for stale dates, missing source coverage, overclaiming from weak sources, and source links that do not support the modeled claim.
- Prefer official or authoritative sources for public facts; mark uncertain claims as assumptions.

### Customer Links

- Review `customers/links.json` when present as curated research/context links for the domain.
- Check link groups have clear purpose, descriptions, relevance notes, and tags that help readers understand why each link matters.
- Confirm links cover the modeled customers, market context, product surfaces, trust/regulatory context, partner ecosystems, or other domain-specific reference areas.
- Flag stale, broken-looking, duplicate, generic, or weakly relevant links, and important missing link categories that would improve customer/domain grounding.
- Check consistency with `customers/insights.json` and `business/competition.json` without requiring every link to become an insight source.

### Competition

- Check that `business/competition.json` defines scope, inclusion logic, caveats, and comparable player categories.
- Verify major direct competitors, regional competitors, substitutes, and adjacent platforms are represented when material.
- Confirm business stats preserve reported metric name, value, period, scope, source title, and source URL.
- Flag unsourced stats, incomparable stats presented as comparable, missing official links, vague competitor descriptions, or category labels that hide real differences.

### Cross-Model Coherence

- Trace customer jobs to product streams and product bricks. Flag important jobs with no plausible implementation path.
- Trace strategy and KPIs to product deployments, product streams, product bricks, data assets, and teams where present.
- Check whether product streams explain customer outcomes rather than just grouping bricks.
- Identify imbalance: too much architecture with thin customer value, or rich customer strategy with weak implementation grounding.

## Output Format

Write a concise but deep review to `_config/product-domains/<group>/<domain>/REVIEW.md`:

1. `Executive assessment`: 3-6 bullets on overall realism, completeness, balance, and readiness for editing.
2. `High-priority findings`: concrete issues that materially weaken the domain model.
3. `Medium-priority findings`: important gaps, inconsistencies, or missed opportunities.
4. `Targeted improvement backlog`: edit-ready actions with affected files and expected outcome.
5. `Open assumptions`: facts that need research, validation, or explicit assumption labels.

For every finding, include:

- `Evidence`: file path and object name or ID.
- `Why it matters`: customer, strategy, business, or implementation impact.
- `Suggested direction`: what a later editing pass should change.

## Quality Bar

- Feedback is specific enough to edit from.
- Findings distinguish realism problems from schema/reference problems.
- The review preserves good existing modeling and does not ask for generic expansion.
- The review favors pragmatic completeness over exhaustive perfection.

## Avoid

- Editing domain source files other than `REVIEW.md` unless the user explicitly asks for a review-and-fix pass.
- Reviewing only JSON syntax while ignoring business coherence.
- Suggesting broad rewrites without naming affected files and IDs.
- Treating all missing information as equally important.

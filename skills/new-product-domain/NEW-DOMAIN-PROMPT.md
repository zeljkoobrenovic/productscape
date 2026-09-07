Use `<DOMAIN-LINK>` as the target company, organization, product, or source link for the domain-definition task. Infer the most suitable product domain from that target and from public evidence.

Create a new product domain under `_config/product-domains/<group>/<domain-id>/` for a business domain in which `<DOMAIN-LINK>` operates. Choose an appropriate existing group or create a new group; never put a domain directly under `_config/product-domains/`. Group names can change, while domain IDs must remain globally unique across groups.

## Skill-Driven Workflow

Before authoring JSON, work through the invocable skills under `skills/`. The
parent `new-product-domain` SKILL.md drives the build order and gates; this prompt is
the input that names the target.

Start with:

- `skills/new-product-domain/SKILL.md` (the build order)
- [domain model](../_references/domain-model.md) (schema, IDs, cross-file map, validate/regen loop)
- the data project's `AGENTS.md`

Then use the per-artifact skill for each phase, in this order:

1. Frame & register → `set-domain-strategy` (also `edit-competition` for the landscape)
2. Customers & strategy → `edit-customers`
3. Architecture → `edit-product-bricks`, then `edit-streams`, then `edit-data-assets`
4. Products & delivery → `edit-products`
5. Teams & operating model → `edit-teams`
7. Validate & audit → `validate-domain`, then `audit-domain-balance`

Load only the skill you need for the current phase; do the phase, validate, continue.

## Task

1. Identify the most suitable `<DOMAIN-LINK>` product domain to model and briefly justify the choice.
2. Create a new domain folder using the toolkit schemas and starter, with modeling depth appropriate to the domain.
3. Infer required files, schemas, and content structure from:
   - the data project's `AGENTS.md`
   - `skills/new-product-domain/SKILL.md` and [domain model](../_references/domain-model.md)
   - the relevant per-artifact `skills/edit-*/SKILL.md`
   - optional domains in the separate productscape-examples repository
   - generator expectations under `_wiring/product-domains/`
4. Populate the new domain with realistic, high-quality source data that fits the repository's conventions and terminology.

## Requirements

- Start with toolkit schemas and `_templates/domain/` for folder structure and required files. Existing example domains are optional.
- Reuse the repository's established modeling language: customers, product strategy, product deployments, teams, product bricks, streams, data assets, start, evidence, and competition.
- Do not invent a new schema if an existing one already fits.
- Treat `_config/**` as the source of truth. Only create or modify generated `docs/**` when generation is explicitly requested.
- If different domains use slightly different structures, identify the most current and internally consistent pattern before creating the new one.
- Keep IDs lowercase and stable. Use short human-meaningful IDs where the schema allows it.
- Ensure all JSON is valid and references are internally consistent.

## Domain Model Requirements

### Research And Competition

- Base the domain on thorough research of `<DOMAIN-LINK>`'s business model, customer groups, marketplace dynamics, product flows, capabilities, competitors, substitutes, and monetization.
- Separate sourced facts, assumptions, and inferred judgments.
- Include competition analysis under `business/competition.json`.
- Build competition analysis from official or authoritative sources where available: company websites, investor relations pages, official press/newsroom pages, official blogs, engineering blogs, official social/company profile pages, and important regional or business pages.
- Identify key players globally and regionally, including major global leaders, strong regional leaders, substitutes, and category-specific competitors where they materially shape the landscape.
- Add a top-level `scope` section explaining inclusion logic and caveats about metric comparability.
- For every competitor, include `id`, `name`, domain-relevant `description`, `hq`, `category`, `primary_regions`, `business_stats`, and `links`.
- Do not invent business metrics. For every business stat, preserve reported metric name, value, period, scope, source title, and source URL.
- Preserve reporting scope exactly. If a company reports platform-wide, regional, or adjacent metrics, label that scope rather than rewriting it into a narrower domain claim.

### Customers, JTBD, Journeys, Strategy, And KPIs

- Define materially distinct customer groups, personas, buyers, users, operators, partners, and beneficiaries where relevant.
- Model jobs to be done as customer progress, not feature usage.
- Journey stories describe how the customer adopts and stays with the product — never how they perform their job. Use exactly these six stages, in this order: `Trigger`, `Discovery`, `Evaluation`, `Trial`, `Engagement`, `Retention`. Task-phase stages ("Preparation", "Award", "Dispatch") are wrong: that content belongs in JTBD steps or streams.
- Define `Trigger` as the pain or event that starts the search for a solution, not a work task.
- In journey stories, define `Discovery` as how customers become aware of the product or offer before active use through channels such as search, referrals, sales outreach, app stores, partner ecosystems, procurement shortlists, internal enablement, or brand touchpoints.
- Define `Evaluation` as how customers decide whether the product is right after discovery and before trial, using alternatives, fit, value, trust, cost, adoption effort, and risk.
- Do not use `Discovery` or `Evaluation` for in-product search, browsing, or task execution.
- Define `Trial` as the first bounded real use (pilot, parallel run, first booking), `Engagement` as the product embedded in routine use, and `Retention` as why the customer stays, renews, expands, and advocates.
- Define product strategy horizons for substantive customer groups: 1-year, 3-year, and 5-year focus, product theme, customer KPI, business KPI, and milestones.
- KPIs should be specific, measurable, and relevant to the domain, with realistic target values based on public information or explicit assumptions. Use a proper tree and minimize one-child branches.

### Product Capabilities, Bricks, And Deployment

- Create a three-level product-brick structure: domain/root group, group/subgroup, and brick.
- Use 20+ product bricks for a mature domain unless the scope is intentionally smaller and justified.
- Product bricks must be realistic, buildable, ownable, and connected to customer or business value.
- Give every brick an `id`. Model each brick's modules under a root-level `layers` array using `ui`, `interfaces`, `worker`, `stateless-service`, `service`, and `integration`; every module needs a short lowercase `id` starting with `module-`.
- Use only these module types: `web-component`, `mobile-component`, `bff`, `api`, `backoffice-interface`, `message-queue`, `message-consumer`, `daemon`, `stateless-service`, `stateful-service`, `service`, and `integration`.
- Model `brickDependencies` through `sourceModuleId` and target `moduleId`; do not use the legacy dependency `interface` field.
- Model product-brick `dataDependencies` with `moduleIds` listing the modules that use or own the data asset; do not use `storeIds` there.
- Product-brick metadata inherits `brickTypes`, `brickStatuses`, and `modulesConfig` from `_config/_shared/product-brick-model.json`; omit them unless the domain diverges.
- Define product capabilities as strategic outcomes, not implementation components, and map them to product bricks and external systems where relevant.
- Model deployment through channels, interfaces, APIs, events, operational workflows, MVP scope, and capability mappings.
- Add data assets where the current domain pattern supports them.

### Teams And Operating Model

- Define a realistic operating model in `teams/teams.json`.
- Use value-stream, platform, enabling, data, reliability, compliance, finance, trust, or operational-control teams where domain-relevant.
- Ensure every product brick has a primary owning team.
- Keep team references from product bricks, deployment surfaces, and data assets resolvable.
- Keep team sizes and group leadership aligned with the current repository convention unless the user asks for a different staffing model.

## Validation Gates

Before calling the work complete:

1. Validate all changed JSON files parse.
2. Run the scoped domain validator:

   ```bash
   python3 productscapes.py validate <new-domain-id> --strict-ids
   ```

3. Run `audit-domain-balance <new-domain-id>` and resolve P1 findings.
4. Run only the relevant generators if generated documentation is explicitly required.
5. Do not regenerate unrelated domains in a dirty worktree.

## Expected Output

- A new folder in `_config/product-domains/<group>/<new-domain-id>/`.
- All appropriate subfolders and source files expected for a mature domain of this type.
- Realistic seed data across relevant JSON files.
- A sourced `business/competition.json` file for the domain.
- A short summary explaining:
  - which product domain was selected
  - which existing domains were used as structural references
  - which skill clusters were used
  - any assumptions made where public information was incomplete
  - validation performed and any remaining gaps

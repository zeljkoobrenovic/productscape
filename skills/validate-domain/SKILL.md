---
name: validate-domain
description: "Validate Productscapes domain JSON, schemas, IDs, and cross-file references, and rebuild the selected domain when generated output is requested. Use after domain-source edits or to diagnose validation and rendering failures."
---

# Validate domain

Read [workspace paths](../_references/workspace.md) and the
[domain model](../_references/domain-model.md). Run the project launcher from the
data repository root so the toolkit validates that repository's sources.

```sh
python3 productscapes.py validate my-domain
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py check-kpis my-domain
```

Use `validate --all` only for an intended full-project scan. Older examples may
have pre-existing model issues; distinguish those from regressions introduced by
the task. Do not suppress failures or describe rendering success as model validity.

The validator checks required artifacts, JSON syntax, artifact schema contracts,
brick/module IDs, supported types, team references, relationships, and the
cross-file links implemented in `skills/scripts/validate-domain-model.py`. The
strict-ID flag adds lowercase and ID-format checks. The KPI checker examines
pyramid shape and referenced metric names. These structural checks do not establish
research quality, realism, or completeness; use `audit-domain-balance` for that.

Fix errors caused by the task and rerun the relevant checks. Preserve unrelated
source work. When a website build is requested or needed to verify rendering:

```sh
python3 productscapes.py build my-domain
```

For a presentation-only change, `build my-domain --sections customers` can scope
rendering to one section. Available sections are start, customers, products,
product-bricks, teams, competition, residuality, and tutorial. The brick section includes
streams and data assets. Generators replace their output directories; inspect
existing docs changes first and keep source edits in JSON or templates.

Report the domain, validation result, actual fixes, generated output, and any
pre-existing findings. Do not call an empty scaffold a completed domain model.

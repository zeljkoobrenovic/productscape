# Productscapes toolkit

This repository contains reusable domain-authoring skills, JSON schemas, shared
model defaults, HTML templates, and Python generators. Real domain examples live
in the separate **productscape-examples** repository.

`productscapes.py` is the public CLI. It reads project data from the current
directory or `--project` and passes `PRODUCTSCAPES_PROJECT` to child scripts.
`_wiring/project_paths.py` distinguishes the toolkit resources from project data.
Never infer the data project from the generator's installation directory.

- `skills/`: canonical authoring and review instructions, references, validators.
- `_config/_schema/`, `_config/_shared/`: reusable model contracts and defaults.
- `_config/product-domains/start/`: default navigation; no example domains.
- `_config/scripts/image-generation/`: optional source image generators.
- `_templates/`: renderer templates; `domain/` is an empty domain starter.
- `_wiring/`: generators and path resolution.
- `project-template/`: a thin launcher and agent instructions for data projects.
- `tests/`: portable CLI integration tests.

Use `skills/new-product-domain/SKILL.md` to author new domains and
`skills/product-domain/SKILL.md` to select a narrower skill. In another project,
source and output paths refer to that project; toolkit resource paths refer here.
The CLI creates scaffolds without invented facts. Skills supply the research and
authoring workflow; examples are optional structural references.

Keep IDs lowercase, domains in discovered groups, and domain IDs unique across
groups. Preserve the JSON and HTML/CSS/vanilla-JavaScript architecture. Use the
Python standard library for the core workflow. Do not require an AI API key to
create, validate, or build a domain. Source-first edits belong in `_config/` or
`_templates/`; `docs/` is generated. Inspect existing changes before rebuilding.

For toolkit changes run `python3 -m unittest discover -s tests -v` and the relevant
existing generator/image tests. Run `python3 skills/scripts/validate-skills.py`
after editing the skill bundle. Keep installed skill copies out of version control.

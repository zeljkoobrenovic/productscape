# Productscapes

Reusable skills and scripts for turning product-domain research into structured
JSON and a static website: customers, jobs to be done, strategy, products, product
bricks, streams, data assets, teams, competition, and residuality stress tests.

**Requires Python 3.10+ and Git.** Creating, validating, and building domains uses
only the Python standard library. No frontend framework, package installation,
or API key is required. Optional image generation uses provider APIs.

## Create your first domain

Clone this repository and run these commands from its root:

```sh
python3 productscapes.py new my-domain --group my-group --name "My Domain"
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py build my-domain
python3 -m http.server 8000 --directory docs
```

Open <http://localhost:8000/>. `new` creates the complete folder structure with
empty, valid collections. It does **not** invent or research a domain. To populate
it, give your coding assistant a request such as:

```text
Use skills/new-product-domain/SKILL.md to model the product domain for <target>.
Use these official sources: <source links>.
Author _config/product-domains/my-group/my-domain/ in this project.
Validate the model and build its website.
```

The [new-domain skill](skills/new-product-domain/SKILL.md) supplies the authoring
workflow; its [input prompt](skills/new-product-domain/NEW-DOMAIN-PROMPT.md) captures
research scope. A fresh clone includes schemas and a starter, so it does not depend
on existing example domains. Research and authoring can also be done manually.

## Keep domain data in another repository

Run from the toolkit root:

```sh
python3 productscapes.py new my-domain --group my-group --project ../my-landscape
cd ../my-landscape
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py build my-domain
```

The new project gets its own source tree, a thin `productscapes.py` launcher,
`productscapes.json`, and agent instructions. The JSON records the toolkit path
relative to that project and its current commit. Initialize Git in the data
project if you want a separate repository. Scripts and templates stay in the toolkit.

`productscape-examples` uses this same interface for the existing example domains.
Clone both repositories beside each other and check out the toolkit commit named
by the examples' `productscapes.json` before building.

## Commands

Run commands from the data project root, or use `--project PATH` from the toolkit.

| Command | Purpose |
| --- | --- |
| `new ID --group GROUP` | Create an empty source scaffold; refuses duplicate IDs |
| `list` | Discover registered domains and groups |
| `info` | Locate the toolkit, data project, schemas, and skills |
| `validate ID --strict-ids` | Validate JSON, schemas, IDs, and modeled references |
| `validate --all` | Check all registered domains |
| `check-kpis ID` | Check KPI pyramid structure and metric references |
| `build ID` | Generate all pages for one domain |
| `build --all` | Generate all registered domains and a site catalog |
| `build ID --sections customers teams` | Rebuild selected sections |
| `skills --target .agents/skills` | Copy portable authoring/review skills into the project |
| `skills --target .claude/skills` | Copy the same skills into another agent's skill directory |
| `images ID --dry-run --lightweight` | Inspect optional image-generation scope |

The CLI builds a domain in this order: start, customers, products, product bricks
(including streams and data), teams, competition, residuality. It also renders
the evidence explorer and optional project start packages. Output goes under
`docs/<group>/<domain-id>/`, with a catalog at `docs/index.html`.

Builds replace the selected generated folders. Keep authored changes in source
JSON and templates. Missing required files or invalid JSON stop a build before
generation starts. Generator failures are reported with a nonzero exit status;
full builds continue with other generators and domains.

## Skills and repository boundaries

There are 15 authoring and review skills. Start with
[product-domain](skills/product-domain/SKILL.md) for routing or
[new-product-domain](skills/new-product-domain/SKILL.md) for complete authoring.
The [model reference](skills/_references/domain-model.md) explains shapes and links.

Canonical skills live in `skills/`. Install copies only if your agent needs a
particular discovery directory; `skills --update` refreshes those copies.
The scripts remain in the toolkit. Installed skills explain how to locate toolkit
resources and use the data project's launcher.

| Toolkit owns | Data project owns |
| --- | --- |
| `skills/`, `_wiring/`, `_templates/` | `_config/product-domains/<group>/<id>/` |
| `_config/_schema/`, `_config/_shared/` | Optional `_config/start-packages/` |
| Default domain navigation | Optional `_config/product-domains/start/apps.json` override |
| `_config/scripts/image-generation/` | Optional `_evidence/database/evidence-files/` and `_evidence/icons/` |
| `project-template/` | Generated `docs/` |

Groups are discovered from disk; domain IDs must be lowercase and unique across
groups. The root `start/` folder contains navigation and is not a domain.
The evidence explorer reads project fragment JSON files, or an existing aggregate
at `_evidence/database/all-evidence.json`. With no evidence it renders an empty
explorer. Building the site does not run external evidence collectors.

## Reproducible toolkit selection

`productscapes.json` pins the toolkit commit. The project launcher refuses a different
commit. `PRODUCTSCAPES_HOME` changes the checkout path, preserving the pin check.
For intentional toolkit development, set `PRODUCTSCAPES_ALLOW_UNPINNED=1`.
After verifying an upgrade, update the project's recorded revision to the new
toolkit commit. Pin checks compare Git HEAD; use a clean toolkit checkout for a
reproducible build. Generated pages also include the build date.

For direct low-level generators, set `PRODUCTSCAPES_PROJECT` to the absolute data
project path. Without it, direct generators use the toolkit checkout as their
project. The public CLI sets this variable automatically.

## Optional images

The `images` command uses the included Gemini generators. Run `--dry-run` first
when scope or cost is uncertain. Credentials are needed only for actual generation;
see the [image generator documentation](_config/scripts/image-generation/README.md)
for providers and options. `--lightweight` limits JTBD and journey imagery to
overviews. Images and media references are written to the selected data project;
run `build` afterward to include them in the website.

## Verify the toolkit

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s _wiring -p test_domain_paths.py -v
python3 -m unittest discover -s _config/scripts/image-generation -p "test_*.py" -v
python3 skills/scripts/validate-skills.py
```

Core commands and tests use Python. Optional shell wrappers and their regression
tests require a POSIX shell. Serve or publish the generated `docs/` directory as
static files. Generated output and installed skill copies are ignored by Git.

MIT licensed; see [LICENSE](LICENSE).

# Product-domain page generators

The runner and all seven `generate-*-docs.py` scripts accept explicit paths.
Paths can be absolute or relative to the directory where you invoke the command;
they are resolved before rendering changes the working directory.

## Build a domain or project

From the toolkit root, build a domain into a selected site directory:

```sh
sh _wiring/product-domains/run.sh \
  --domain-dir ../productscape-examples/_config/product-domains/vortexcp/solvari-home-improvement-marketplace \
  --output-dir ../published-site \
  --templates-dir ./_templates \
  --navigation-file ./_config/product-domains/start/apps.json \
  --shared-config-dir ./_config/_shared
```

The domain folder must use
`<project>/_config/product-domains/<group>/<domain-id>/`. Its path selects the data
project automatically, including its evidence and start-package inputs. You can
also pass the folder as the first positional argument instead of `--domain-dir`.

Build every registered domain by supplying the project and `--all`:

```sh
sh _wiring/product-domains/run.sh \
  --project ../productscape-examples --all \
  --output-dir ../published-site
```

The runner forwards its arguments to `python3 productscapes.py build`. It also
accepts `--sections start customers products product-bricks teams competition
residuality` and `--verbose`. Choose a domain or pass `--all`; running without a
selection reports the missing input.

## Generate one section

```sh
python3 _wiring/product-domains/generate-customers-docs.py \
  --domain-dir ../productscape-examples/_config/product-domains/vortexcp/solvari-home-improvement-marketplace \
  --output-dir ../published-site \
  --templates-dir ./_templates
```

The same options work for start, customers, products, product bricks, teams,
competition, and residuality generators. The `products` generator publishes to
the `product-deployments` section.

| Input | Default or behavior |
| --- | --- |
| `--domain-dir PATH` or positional folder | Domain source folder; selects its project |
| `DOMAIN_ID --project PATH` | Resolve a domain ID within that data project |
| `--output-dir PATH` | Site root; defaults to `<project>/docs` |
| `--templates-dir PATH` | Root containing section templates and `_imports`; defaults to toolkit `_templates` |
| `--navigation-file PATH` | Domain navigation `apps.json`; defaults to project navigation, then toolkit navigation |
| `--shared-config-dir PATH` | Shared model definitions; defaults to toolkit `_config/_shared` |
| `--name TEXT`, `--description TEXT` | Direct-generator metadata overrides; defaults to the domain's `start/config.json` |

Output keeps the site layout
`<output-dir>/<group>/<domain-id>/<section>/index.html`. The full build also puts
the catalog, evidence explorer, and start packages under the same output root and
uses the selected template root for those pages. A direct section generator
renders only that section.

The legacy direct-generator invocation remains supported:

```sh
python3 _wiring/product-domains/generate-start-docs.py \
  my-domain "Domain name" "Domain description" \
  --project ../my-data-project --output-dir ../published-site
```

Explicit arguments take precedence over inherited project/render settings. A
domain folder and an explicit `--project` must identify the same project. Missing
input paths, an output root that overlaps inputs, and output paths escaping the
site directory are rejected before rendering. Use `--help` on the runner or any
generator to inspect its arguments without creating output.

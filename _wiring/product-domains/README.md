# Product-domain page generators

The runner and all eight `generate-*-docs.py` scripts accept explicit paths.
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
accepts `--sections start customers products product-bricks competition value-growth
residuality tutorial` and `--verbose`. Choose a domain or pass `--all`; running without a
selection reports the missing input.

## Generate one section

```sh
python3 _wiring/product-domains/generate-customers-docs.py \
  --domain-dir ../productscape-examples/_config/product-domains/vortexcp/solvari-home-improvement-marketplace \
  --output-dir ../published-site \
  --templates-dir ./_templates
```

The same options work for start, customers, products, product bricks,
competition, value-growth, residuality, and tutorial generators. The `products` generator publishes to
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

The tutorial generator reads `tutorial/tutorial.json`, its referenced local images, and domain metadata;
it does not require evidence or other model artifacts. Missing tutorials render
an empty page, drafts are labeled, and `ready` tutorials must pass completeness
checks before the previous tutorial page is replaced. Concept and overview images are copied
from `tutorial/media/` and link to their full versions in a new tab. Generating
images is a separate, optional `images my-domain --kind tutorial` action.

The `value-growth` generator reads optional `business/value-growth.json` and its
customer, product and competitor references. It renders value and pricing units,
selling and growth assessments, public pricing examples, activation, economics and
an interactive TAM/SAM/SOM scenario calculator under Business → Value & Growth.
Observed evidence and illustrative assumptions are labeled. Missing models render
an empty page. Validation and build preflight reject invalid references and market
inputs before replacing pages. No API keys or external Python packages are needed.

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

## Value & Growth rendering

The Business menu links to `value-growth/index.html`. The page uses the shared
tabs from `_templates/_imports/tabs/`, with one panel visible at a time:

| Tab | URL fragment | Contents |
| --- | --- | --- |
| Value & monetization | `#value` | Customer outcomes, value and pricing units, offering cards, public pricing examples |
| Selling & positioning | `#selling` | Selling motions, growth positioning, provider perspectives |
| Activation & growth | `#activation` | Entry models and provider examples, freemium/trial fit, conversion, first and repeated value, expansion, friction, growth mechanisms |
| Market opportunity | `#market` | Market boundaries, context, editable TAM/SAM/SOM scenarios and assumptions |
| Business economics | `#economics` | Economic metrics, measurement limits and constraints |
| Sources & evidence | `#sources` | Evidence definitions and dated source links |

Tabs appear when their source content is present; a ready model renders all six.
The default is Value & monetization, or the first available tab for a partial
draft. Tab selection updates the URL and supports browser history and left/right
arrow keys. Links to a source, provider or offering reveal the containing tab
before scrolling to the item. Printing or disabling JavaScript shows all panels;
the calculator requires JavaScript to change assumptions.

Optional `entryStrategy` adds entry-model cards and sourced provider examples.
Optional `activation.entryOffer` adds an assessment to each offering's activation
card, including freemium and trial fit, evaluation scope, limits, paid triggers
and conversion measures. Its `modelIds` must reference `entryStrategy.models`.
Links such as `#entry-model-freemium` and `#entry-offer-online-checkout` open the
Activation tab when those authored IDs exist. Older models still render without
these additions; a draft entry strategy can render before segments are authored.

Keep layout changes in `_templates/value-growth/`. `index.html` owns the page
shell and shared imports; `value-chain.html` owns the four introductory value
cards; `style.css` owns local spacing and presentation; `script.js` handles links
within panels and the calculator. The generator assembles the panels from
`business/value-growth.json`. Edit templates or source JSON, then regenerate the
page.

The page matches the other domain pages with a white background, unboxed header,
logo, typography and shared breadcrumbs. Cards have 40px padding on desktop;
at widths of 800px or less they use 32px vertically and 24px horizontally.
Card grids use 36px gaps; headings, labels,
paragraphs, related links and evidence notes have distinct spacing. Tables scroll
within their container on narrow screens, while card grids become one column.
The introductory value cards retain two columns on mobile.
Strategy cards wrap into fewer columns when needed to preserve their reading width.

After a layout change, regenerate the affected section and check all tabs on
desktop and mobile, including source links, the Business menu and calculator.
Run the toolkit tests required by `AGENTS.md`. Rebuild `start` as well when the
menu changes.

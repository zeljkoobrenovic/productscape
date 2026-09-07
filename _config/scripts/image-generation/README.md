# Product Domain Image Generation

This folder contains source-first scripts that scan product-domain models, generate supporting imagery, save files beside the relevant source JSON, and update media references when needed.

Sources live in `_config/product-domains/<group>/<domain-id>/`. All image scripts discover groups through `_wiring/domain_paths.py`; group names can change without script edits. Python scripts take the bare domain ID with `--domain`, for example `--domain ride-sharing-marketplace`. The `run.sh` wrapper takes a path to the domain folder and selects its data project automatically. Domain IDs must be unique across groups. The shared root-level `start/` folder is excluded from discovery.

## What It Does

- finds every `_config/product-domains/<group>/<domain-id>/customers/customers.json`
- reads every customer plus:
  - `jobsToBeDone` and their steps
  - `customerJourneyStories` and their stages
- builds a better image prompt from:
  - customer name and description
  - JTBD name, outcome, description, and capability mappings
  - journey summary, linked jobs, and stage narratives
  - the style cues from `_config/scripts/image-generation/jtbd-cartoon-prompt.txt` or `_config/scripts/image-generation/customer-journeys.md`
- calls either the OpenAI Images API or the Gemini Nano Banana image API for JTBD images, and the Gemini Nano Banana image API for journey images
- writes image files into `customers/media/`
- patches `media` entries in JSON if missing or stale
- supports `--lightweight` JTBD and journey runs that create only job/journey overviews, without creating step/stage targets or media references
- generates one rich, square customer-role portrait per customer in the same colored cartoon style as the customer-relations overview, saves it in `customers/icons/`, and updates the existing `icon` field
- generates one Gemini Nano Banana illustration for every residuality stressor, writes it into `residuality/media/`, and patches the stressor's `media` entry

## Requirements

- Python 3.10+
- `OPENAI_API_KEY` for the OpenAI Images API script
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` for the Gemini Nano Banana script
- outbound network access when you actually run the script

The API scripts use only Python's standard library. The general missing-domain-icon generator also needs `ffmpeg` and `ffprobe` for monochrome icon post-processing. The dedicated customer portrait generator preserves the returned image directly and does not need those tools.

## Usage

For a separate data repository, prefer its launcher:

```sh
python3 productscapes.py images my-domain --dry-run --lightweight
```

For the direct Python commands below, run from the toolkit root and set
`PRODUCTSCAPES_PROJECT` to the absolute path of your data repository. Named example
domains are available in productscape-examples; substitute your own domain ID.


From the repository root:

Rich customer icons via Gemini Nano Banana API:

```bash
export GEMINI_API_KEY=...
python3 _config/scripts/image-generation/generate_customer_icons_gemini_nanobanana_api.py --domain ride-sharing-marketplace --dry-run
python3 _config/scripts/image-generation/generate_customer_icons_gemini_nanobanana_api.py --domain ride-sharing-marketplace --limit 2
python3 _config/scripts/image-generation/generate_customer_icons_gemini_nanobanana_api.py --domain ride-sharing-marketplace --customer drvu
python3 _config/scripts/image-generation/generate_customer_icons_gemini_nanobanana_api.py --domain ride-sharing-marketplace --overwrite
python3 _config/scripts/image-generation/generate_customer_icons_gemini_nanobanana_api.py --domain ride-sharing-marketplace --json-only
```

Each portrait uses the domain and customer descriptions, customer group, priorities, jobs, and any customer relations to depict a recognizable role with clothing, props, and a compact setting. The composition is square, with friendly characters, crisp outlines, blue/teal/green/orange accents, generous margins, and no text. It matches the character style described by the relations generator; it does not extract characters from an existing relations image.

Files are named `customers/icons/customer-<customer-id>-portrait.<format>` (PNG, JPEG, or WebP as returned by Gemini). This gives customers distinct images even when they previously shared `customer.png`. Existing line-art files are preserved, and the customer's `icon` switches to the portrait filename only after a nonempty image exists. The existing page templates and docs generator already support these icon references.

The default run creates missing portraits and upgrades legacy icon references. `--skip-existing` refers to the new portrait files, so an existing legacy icon does not prevent an upgrade. `--overwrite` regenerates portraits; `--json-only` links portraits already on disk without creating references to missing files. `--limit` caps API calls across all selected domains. `--customer` selects one customer id, normally together with `--domain`.

JTBD images via OpenAI Images API:

```bash
export OPENAI_API_KEY=...
python3 _config/scripts/image-generation/generate_jtbd_images_openai_images_api.py --dry-run
python3 _config/scripts/image-generation/generate_jtbd_images_openai_images_api.py --domain food-and-nutrition-product-platform --lightweight
python3 _config/scripts/image-generation/generate_jtbd_images_openai_images_api.py --domain food-and-nutrition-product-platform --limit 4
python3 _config/scripts/image-generation/generate_jtbd_images_openai_images_api.py --domain food-and-nutrition-product-platform --overwrite
```

JTBD images via Gemini Nano Banana API:

```bash
export GEMINI_API_KEY=...
python3 _config/scripts/image-generation/generate_jtbd_images_gemini_nanobanana_api.py --dry-run
python3 _config/scripts/image-generation/generate_jtbd_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --lightweight
python3 _config/scripts/image-generation/generate_jtbd_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --limit 4
python3 _config/scripts/image-generation/generate_jtbd_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --overwrite
```

Customer journey images via Gemini Nano Banana API:

```bash
export GEMINI_API_KEY=...
python3 _config/scripts/image-generation/generate_journey_images_gemini_nanobanana_api.py --dry-run
python3 _config/scripts/image-generation/generate_journey_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --lightweight
python3 _config/scripts/image-generation/generate_journey_images_gemini_nanobanana_api.py --domain bike-mobility --json-only
python3 _config/scripts/image-generation/generate_journey_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --limit 4
python3 _config/scripts/image-generation/generate_journey_images_gemini_nanobanana_api.py --domain food-and-nutrition-product-platform --overwrite
```

Run the image generators for a domain folder, using lightweight JTBD and journey generation:

```bash
bash _config/scripts/image-generation/run.sh \
  ../productscape-examples/_config/product-domains/vortexcp/solvari-home-improvement-marketplace \
  --lightweight
```

The folder can be an absolute path or a path relative to the directory where you run the command. It must identify `<project>/_config/product-domains/<group>/<domain-id>/`. The wrapper derives `PRODUCTSCAPES_PROJECT` from that folder, overriding any inherited value, so it works from another directory without a separate project setting. Missing folders and paths outside this layout are rejected before any generator runs.

The wrapper runs customer portraits first, then JTBD, journeys, relations, and residuality images. Full runs also generate the remaining domain icons. Lightweight mode still includes one portrait per customer. The general `generate_missing_domain_icons_gemini_nanobanana_api.py` script delegates customer work to the same portrait generator when run directly; the wrapper passes `--skip-customer-icons` to avoid repeating that work. KPI, start-page, brick, and capability icons retain their existing monochrome style.

Residuality stressor images via Gemini Nano Banana API:

```bash
export GEMINI_API_KEY=...
python3 _config/scripts/image-generation/generate_residuality_images_gemini_nanobanana_api.py --dry-run
python3 _config/scripts/image-generation/generate_residuality_images_gemini_nanobanana_api.py --domain ride-sharing-marketplace --limit 2
python3 _config/scripts/image-generation/generate_residuality_images_gemini_nanobanana_api.py --domain ride-sharing-marketplace --overwrite
```

Useful flags:

- `--domain <id>` limits work to one domain
- `--limit N` caps the number of generated images
- `--skip-existing` avoids regenerating files already on disk
- `--overwrite` regenerates image files even if they already exist
- `--json-only` updates missing `media` references without calling the API
- `--lightweight` makes the JTBD and journey generators create only job/journey overview images; it skips individual JTBD steps and journey stages and does not add media references for them
- `--dry-run` prints planned actions only
- `--model` defaults to `gpt-image-1.5` for OpenAI and `gemini-3-pro-image-preview` for Gemini
- `--api-key-env` on the Gemini script lets you switch between `GEMINI_API_KEY` and `GOOGLE_API_KEY`
- `generate_journey_images_gemini_nanobanana_api.py` creates:
  - one image for each `customerJourneyStories[]`
  - one image for each `customerJourneyStories[].stages[]`
- `generate_jtbd_images_*` creates:
  - one image for each `jobsToBeDone[]`
  - one image for each `jobsToBeDone[].steps[]`
- `generate_customer_relations_images_gemini_nanobanana_api.py` creates:
  - one relationship-map illustration per domain from `customers/relations.json`
    (saved as `customers/media/relations-overview.png`, referenced via a top-level
    `media` entry in `relations.json` and shown at the top of the Relations tab;
    the reference is only written once the image exists)
- `generate_customer_icons_gemini_nanobanana_api.py` creates:
  - one square role illustration per customer, referenced through `customer.icon`
  - files in `customers/icons/`, preserving colors, filled whites, and margins
  - no customer `media` entries or changes to JTBD/journey media
- `generate_residuality_images_gemini_nanobanana_api.py` creates:
  - one landscape illustration per `stressors[]` item
  - files named `residuality/media/stressor-<stressor-id>.<format>` using the image format returned by Gemini
  - an image `media` entry on each generated stressor for the residuality page

## Notes

- Image scripts update only their source JSON files. They do not regenerate `docs/`.
- Existing non-image media entries are preserved.
- Lightweight runs preserve any existing step/stage images and media references; omitting `--lightweight` retains full overview plus detail generation.
- Existing user changes elsewhere in the worktree are untouched.
- A safe first run is `--dry-run` or `--json-only` on one domain before doing full image generation.
- Customer portrait generation retries transient failures (including HTTP 429), saves each completed icon reference before moving to the next customer, and recognizes existing portraits in every supported image format.

## Offline Verification

The customer portrait checks use temporary domain fixtures and simulated API responses; they do not generate paid images or edit product-domain data:

```bash
python3 -B -m unittest discover -s _config/scripts/image-generation -p 'test_*.py'
```

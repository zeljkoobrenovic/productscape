# Tutorial JSON and reading structure

The toolkit contract is `_config/_schema/tutorial.schema.json`. Locate the toolkit
with `python3 productscapes.py info`; installed copies of this skill keep this
reference and the worked example but do not relocate schemas or generators.

Each tutorial is an object in
`_config/product-domains/<group>/<domain>/tutorial/tutorial.json`.
Use `schemaVersion: "1.0"`, the folder's `domainId`, `status: "draft" | "ready"`,
and a descriptive `title`. `updated` is an optional author-review date in
`YYYY-MM-DD` form; builds do not change it. Drafts can omit unfinished sections.
Ready tutorials require the core fields below and nonempty core collections.

| Field | Shape and teaching purpose |
| --- | --- |
| `audience` | String describing the reader and any assumed knowledge. |
| `scope` | String explaining boundaries and relevant local context. |
| `learningGoals` | Strings stating what the reader will be able to explain or do. |
| `introduction` | `whatItIs`, `whyItMatters`, `familiarComparison`, `whereComparisonBreaks`: all strings. Begin with the everyday need. |
| `participants` | Objects with `name`, `role`, `caresAbout`. Explain differing interests. |
| `participantsOverview` | Optional object with `illustrationPrompt` and/or `media` for a map of the participants and their relationships. Requires participants. |
| `concepts` | Objects with `term`, `meaning`, `example`, `whyItMatters`; optional `illustrationPrompt` and `media`. Definitions must work without other unexplained terms. |
| `history` | Objects with `period`, `change`, `whyItMatters`; optional `sourceUrl`. Broad periods are valid; list in time order. |
| `historyNote` | Optional string framing the historical selection, e.g. a country's experience rather than a universal chronology. |
| `walkthrough` | `title`, `setup`, `steps`, `outcome`; optional `illustrationPrompt` and `media`. Each step has `title`, `whatHappens`, `whyItMatters`, and optional `watchOut`. Teach a whole case, including an exception. |
| `valueAndIncentives` | Objects with `title`, `explanation`, `example`. Cover benefits, funding/costs, and incentives using the domain's own economics. |
| `challenges` | Objects with `title`, `whyHard`, `tradeOff`, `example`, `commonApproach`. Explain consequences and limitations of the response. |
| `misconceptions` | Objects with `belief`, `reality`. Correct a likely misunderstanding without shaming the reader. |
| `takeaways` | Strings that connect the main ideas into a reusable understanding. |
| `knowledgeChecks` | Objects with `question`, `answer`, `explanation`. The answer and explanation are hidden until the reader opens a disclosure. |
| `nextQuestions` | Optional strings with useful questions for a practitioner. |
| `furtherReading` | Optional objects with `title`, `url`, `whyRead`. Use direct HTTP(S) URLs to useful resources. No evidence-model IDs. |

All prose values are plain text. Use `\n\n` inside a string for paragraphs.
Do not put a whole tutorial in one text field, encode HTML, or add Markdown links;
the renderer escapes text and renders the explicit URL fields as links. Keep
strings nonblank. Omit optional fields instead of giving them empty strings.

The renderer supplies section headings, stable contents anchors, estimated reading
time, and responsive/print styles. Empty optional sections are hidden. An absent
tutorial produces an honest empty page; a partial tutorial shows a draft notice.
Reading, contents navigation, and native answer disclosures work without JavaScript
or network access. Opening the local HTML is enough to read it.

The worked example at `../assets/example-tutorial.json` is deliberately compact.
It shows explanatory depth within entries; a full tutorial can expand the same
structure without adding more concepts than the reader needs.

## Optional concept illustrations

Keep the explanation complete without images. A concept can add an
`illustrationPrompt` string describing a useful teaching scene, exact short
labels, and any distinctions the image must preserve. Images use the repository's
`media` convention, with paths relative to the tutorial folder:

```json
{
  "id": "concept-illustration",
  "type": "image",
  "src": "media/concept-reservation.png",
  "title": "Reservation",
  "alt": "A borrower reserves a drill on a calendar before collecting it from the library.",
  "caption": "Booking the drill and physically borrowing it happen at different times."
}
```

Place image objects in the concept's `media` array. `type`, `src`, and descriptive
`alt` text are required; `id`, `title`, and `caption` are optional. IDs are unique
within a concept. Files must exist and be nonempty, beneath `tutorial/media/`,
using PNG, JPEG, or WebP extensions and filename components made of letters,
digits, hyphens, or underscores. Remote URLs and paths that leave the tutorial
folder are not supported. Do not embed base64 image bytes in the JSON.

Generate with `python3 productscapes.py images my-domain --kind tutorial`, or use
the toolkit's `_config/scripts/image-generation/generate_tutorial_images_gemini_nanobanana_api.py`
directly with `--domain-dir`. `--dry-run --show-prompts` previews prompts without
credentials or writes, `--limit 1` makes one image for review, and `--json-only`
links existing files. The generator saves its own `concept-illustration` entry,
reuses existing images, and preserves other media and reviewed alt text/captions.
Use `--concept` with a term or its printed key and `--overwrite` for a revision.
See the image-generation README in the toolkit for provider options.

Review visual accuracy, legibility on a phone, and the meaning of every arrow.
Replace generic generated alt text with a concise description of the actual
scene; use the caption to state the lesson and any needed qualification. The
renderer places illustrations after the definition, copies referenced image
files into the tutorial output, and opens the full image in a new tab when clicked.
Saved `.prompt.txt` files remain in the source folder for reproducibility.

## Optional section overviews

After the concepts, consider a participant map or a walkthrough overview when it
connects ideas the individual concept illustrations cannot. Use the same image
objects and path rules above:

- `participantsOverview.illustrationPrompt` and `participantsOverview.media`
  describe a map placed before the participant descriptions. Distinguish who
  provides resources, decides, does the work, and experiences the consequences.
  Label each connection; ownership and management links are different from cash.
- `walkthrough.illustrationPrompt` and `walkthrough.media` describe a story placed
  after the setup and before the detailed steps. Keep the cast and reading order
  consistent, include a complication, and show hypothetical outcomes as conditional.
  Separate alternative cases instead of blending them into one sequence.

Default image runs include concepts and overviews configured with a prompt or
media. Use the direct image script with `--section participants` or
`--section walkthrough` to generate an overview from the existing prose even
without a custom prompt. `--section concepts` and `--concept` keep generation
limited to concepts. The source files and generated media IDs for overviews are
`participants-overview` and `walkthrough-overview`; captions and alt text stay
editable. All illustrations open in a new tab.

Choose a few useful overviews rather than illustrating every paragraph. A broad
map and a connected story usually add more than another picture of a definition.
Review every arrow, label, amount, and branch against the prose before rendering.

## Direct preview

When the surrounding domain has incomplete or unrelated artifacts, the tutorial
generator can validate and render only this artifact. It needs the domain folder
and its `start/config.json`, not customer, architecture, or evidence files:

```sh
python3 /path/to/toolkit/_wiring/product-domains/generate-tutorial-docs.py \
  --domain-dir /path/to/project/_config/product-domains/my-group/my-domain \
  --output-dir /path/to/preview
```

Output is `/path/to/preview/my-group/my-domain/tutorial/index.html`. The generator
also supports `--project`, `--templates-dir`, and the shared render-path options.
Use the project launcher's `build my-domain --sections tutorial start` for the
normal site workflow, which exposes the tutorial in domain home navigation.

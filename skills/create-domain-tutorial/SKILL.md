---
name: create-domain-tutorial
description: "Create or revise a beginner tutorial introducing a product domain to someone from a different field. Explain its purpose, people, key concepts, short history, everyday workflow, economics, and challenges in plain language; author tutorial/tutorial.json and render its reading page. Use for domain introductions and onboarding primers, including when no evidence model exists."
---

# Create a domain tutorial

Help a capable adult who is new to this field understand what happens, why it
happens, and what makes it difficult. The result is a general introduction to the
domain, useful before reading its strategy or architecture. It should make sense
without knowing Productscape, its model, or the author's company.

Author `_config/product-domains/<group>/<domain>/tutorial/tutorial.json` in the
data project. The toolkit renders it to `docs/<group>/<domain>/tutorial/index.html`
using `_templates/tutorial/`. Keep prose in JSON and presentation in templates.

## Establish the reader and boundary

Read [workspace paths](../_references/workspace.md), then locate the target with
`python3 productscapes.py list`. Read `start/config.json`, the domain brief if it
exists, and an existing tutorial before editing. Consult other domain files only
when they clarify the domain's meaning or boundaries; a full model review is not
a prerequisite.

Infer the intended domain and audience from the request and project context.
Ask when the domain is ambiguous or a jurisdiction/specialization would change
the explanation materially. Otherwise proceed with a curious adult reader who
knows no industry terminology. If the reader's previous field is known, use one
or two bridges from it without assuming everyone has that background.

State the scope in the tutorial: what is covered, adjacent areas left out, and
any geographic or business-model limits. Default to a focused 15–20 minute
introduction, roughly 1,800–2,600 words; adjust to the request and subject. These
are writing targets, not quotas. Prefer useful explanation over filling sections.

If the user requests a new domain, use the CLI's empty scaffold with a suitable
discovered group. Author only the tutorial unless broader modeling is requested.
Do not start a full `new-product-domain` research workflow to write a primer.

## Build an explanation a newcomer can follow

Read [the JSON and reading structure](references/tutorial-format.md) before
authoring. The [worked example](assets/example-tutorial.json) demonstrates the
format and teaching style with tool lending. Its fictional walkthrough is labeled;
its local historical examples have direct sources. Use its depth and reasoning,
not its domain facts, as a guide.

Sketch the learning goals and one ordinary situation before drafting. Carry that
situation through the concepts, workflow, and challenges so the reader does not
have to learn a new scenario in every section. Write a connected explanation in
the reading order supported by the renderer:

1. **Start with a recognizable need.** Say what the domain does, for whom, and
   why it exists. Give a familiar comparison and say where it stops being useful.
2. **Introduce the people.** Explain who uses, pays, provides, operates, and bears
   risk where these differ. Describe what each wants, in ordinary language.
3. **Teach the essential concepts.** For each term, give a plain definition, a
   concrete example, and why the distinction matters. Explain it at first use;
   the concepts section is a reference, not permission to use unexplained words
   earlier. Show commonly confused distinctions such as a promise versus delivery.
4. **Give a little history.** Choose a few turning points that explain present
   practices: the earlier problem, what changed, and the consequence. Include
   social, organizational, or regulatory changes where relevant, not just new
   technology. Identify local examples as local; avoid an inevitable-progress
   story or claiming one company invented the entire field.
5. **Walk through one complete case.** Name the people and follow the work from
   need to outcome, including handoffs, a decision, and a plausible exception.
   Describe what happens behind the visible product. End with what success means
   for the people involved. Label invented characters and illustrative numbers.
6. **Explain value and incentives.** Show who benefits, who pays or funds the
   service, major costs, and how participants' interests can conflict. For public
   services, explain resources and public outcomes rather than forcing a profit
   model. Discuss signs of success without inventing market statistics or targets.
7. **Make the hard parts concrete.** For each key challenge, describe its cause,
   who feels the consequences, the competing needs, an example, and a common
   response with its limitations. A list of generic words such as “scale”,
   “trust”, and “regulation” is not an explanation.
8. **Help the reader use the explanation.** Correct likely misconceptions,
   recap the main ideas, add short application questions with explained answers,
   and suggest questions they can ask a practitioner. Answers must be learnable
   from this tutorial; use reasoning about the case rather than date trivia.

Use short paragraphs and concrete verbs. Keep the reader's intelligence intact:
simple language does not mean a childish voice. Use industry terms only when the
reader will encounter them again; expand necessary acronyms and explain their
meaning. Avoid product pitches, architecture inventories, assumed software
knowledge, and unexplained Productscape labels such as “bricks” or “streams”.

## Ground claims without requiring an evidence model

Existing evidence can help, but evidence IDs, customer IDs, and architecture
cross-references are not required. Stable background explanations can stand on
their own. Verify uncertain facts, named historical dates, current market claims,
and legal or regulatory statements with reliable sources. Prefer primary sources
for specific claims. Link a historical claim with its optional `sourceUrl`, and
use a short `furtherReading` list for other references, explaining why each helps.

Distinguish general patterns, local practices, historical facts, interpretations,
and fictional teaching examples in the prose. Explain geographical variation
where it changes the story. If verification is unavailable, omit unsupported
precision, use a defensible broader period, or state the uncertainty. Do not
invent citations, make every sentence carry a citation, or block the tutorial on
building an evidence database.

## Write, review, and render

Use `_config/_schema/tutorial.schema.json` from the toolkit returned by
`python3 productscapes.py info`. The empty starter is
`_templates/domain/tutorial/tutorial.json`. Copy/adapt it if an older domain has no
tutorial yet. Preserve useful authored content during revisions. Strings are
plain text, with blank lines for paragraphs; HTML and Markdown are not rendered.

Mark `status` as `ready` only after the introduction, people, concepts, history,
walkthrough, value, challenges, misconceptions, takeaways, and knowledge checks
are written and reviewed. An empty scaffold or incomplete preview stays `draft`.
The validator checks shape and minimum completeness; it cannot judge teaching.

Review from the outsider's perspective: can they explain why this domain exists,
follow the case without looking up words, distinguish the essential concepts,
and describe a real tradeoff? Remove repetition, undefined terms, unsupported
precision, and trivia. Check that each learning goal is taught and that the
answers explain the reasoning. Read the opening aloud if it feels abstract.

From the data project, run:

```sh
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py build my-domain --sections tutorial start
```

Inspect the generated page at a narrow and wide width when browser tools are
available. Check the reading order, contents links, history, complete walkthrough,
and answer disclosures. If illustrations are requested, begin with the concepts:
choose scenes that clarify an actual distinction, write optional `illustrationPrompt`
directions, and use `images my-domain --kind tutorial`. Follow the
[illustration contract](references/tutorial-format.md#optional-concept-illustrations)
to review visual accuracy, write useful alt text and captions, and verify that
images open in a new tab. Keep the prose understandable without images.
For additional illustrations, use a participant map or walkthrough overview to
connect the ideas; follow the [section overview format](references/tutorial-format.md#optional-section-overviews).
Choose a few teaching visuals, preserve alternative cases and uncertainty, and
review the relationships and reading order before publishing.
Existing unrelated validation issues should be reported
separately; don't expand the task into repairing the entire domain. For a tutorial
preview independent of other artifacts, use the direct generator described in
the format reference; it validates the tutorial itself before replacing output.

Report the audience/scope, source JSON and generated page paths, checks performed,
and any material uncertainty. Do not present a draft as a finished tutorial.

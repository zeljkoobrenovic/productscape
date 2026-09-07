# Productscape data project

This project owns `_config/product-domains/<group>/<domain-id>/` and optional
`_evidence/` and `_config/start-packages/` data. `docs/` is generated output.
Use lowercase IDs, globally unique domain IDs, and groups discovered from disk.
Preserve existing uncommitted source changes and inspect generated changes before rebuilding.

The scripts, schemas, templates, and canonical skills belong to the separate
**productscapes** toolkit. Run `python3 productscapes.py info` to locate it.
`productscapes.json` records its relative checkout path and pinned commit;
`PRODUCTSCAPES_HOME` may override the path. Keep shared implementation changes
in the toolkit; the local `productscapes.py` only forwards commands.

Use the toolkit's `skills/new-product-domain/SKILL.md` to author a complete domain,
`skills/product-domain/SKILL.md` to route smaller edits, and its `_config/_schema/`
for artifact shapes. In skills, source and output paths refer to this project;
`skills/`, `_templates/`, `_wiring/`, `_config/_schema/`, `_config/_shared/`, and
`_config/scripts/` refer to the toolkit. Installed skill references are relative
to the installed skill directory. Example domains are optional references.

Run commands from this project root:

```sh
python3 productscapes.py new my-domain --group my-group
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py build my-domain
```

`new` creates an empty scaffold. Author researched content before treating it as
a complete model. Keep evidence, assumptions, and inferences distinct. Model
customer value and KPIs before delivery, bricks, data ownership, and teams.
Validate references after edits. Regenerate only the selected domain when needed.
Templates use HTML, CSS, and vanilla JavaScript; preserve the no-framework approach.
Generated pages must work as static assets.

Image generation is optional and separate from builds. Run
`python3 productscapes.py images my-domain --dry-run --lightweight`
to inspect scope before using the provider APIs when scope or cost is uncertain.

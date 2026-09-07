# Toolkit and data workspace

Run `python3 productscapes.py info` from the data project to locate its toolkit.
Source `_config/product-domains/`, optional `_evidence/`, and generated `docs/`
paths refer to the data project. `skills/`, `_wiring/`, `_templates/`,
`_config/_schema/`, `_config/_shared/`, and `_config/scripts/` refer to the toolkit.
Installed skills use relative links for shared references.

Use the project launcher for executable commands:

```sh
python3 productscapes.py list
python3 productscapes.py new my-domain --group my-group
python3 productscapes.py validate my-domain --strict-ids
python3 productscapes.py check-kpis my-domain
python3 productscapes.py build my-domain
```

Use schemas and `_templates/domain/` for required source shapes. The scaffold
contains empty collections, not a mature model. Existing data in a separate
productscape-examples checkout can inform depth and structure, but is optional.
Never assume a named reference domain is present in a fresh toolkit clone.
Choose domain-appropriate depth; do not invent facts to meet example counts.

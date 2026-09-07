"""Dependency-free structural checker for the _config JSON artifacts.

Implements the small JSON-Schema subset the repo's schemas under
_config/_schema/ actually use — no external jsonschema dependency:

  type (string or list), properties, required, items, enum, pattern,
  minItems, additionalProperties (false -> unknown keys are errors),
  $ref (to #/$defs/... within the same schema file), and the custom
  keyword x-banned (a list of property names that must NOT be present,
  used to keep retired/legacy fields from creeping back in).

Unknown keywords are ignored, so schemas stay forward-compatible with
real JSON Schema tooling.
"""
import json
import re

_TYPE_CHECKS = {
    'object': lambda v: isinstance(v, dict),
    'array': lambda v: isinstance(v, list),
    'string': lambda v: isinstance(v, str),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'boolean': lambda v: isinstance(v, bool),
    'null': lambda v: v is None,
}


def _resolve_ref(ref, root_schema):
    if not ref.startswith('#/'):
        raise ValueError(f'unsupported $ref: {ref}')
    node = root_schema
    for part in ref[2:].split('/'):
        node = node[part]
    return node


def validate(value, schema, root_schema=None, path='$', errors=None):
    """Validate value against schema; returns a list of error strings."""
    if errors is None:
        errors = []
    if root_schema is None:
        root_schema = schema

    if '$ref' in schema:
        return validate(value, _resolve_ref(schema['$ref'], root_schema), root_schema, path, errors)

    expected = schema.get('type')
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS[t](value) for t in types):
            errors.append(f'{path}: expected {"|".join(types)}, got {type(value).__name__}')
            return errors

    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: value {value!r} not in allowed set {schema["enum"]}')

    if isinstance(value, str) and 'pattern' in schema:
        if not re.search(schema['pattern'], value):
            errors.append(f'{path}: {value!r} does not match pattern {schema["pattern"]}')

    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:
                errors.append(f'{path}: missing required property "{key}"')
        for key in schema.get('x-banned', []):
            if key in value:
                errors.append(f'{path}: property "{key}" is retired and must not be used')
        props = schema.get('properties', {})
        for key, subschema in props.items():
            if key in value:
                validate(value[key], subschema, root_schema, f'{path}.{key}', errors)
        if schema.get('additionalProperties') is False:
            for key in value:
                if key not in props:
                    errors.append(f'{path}: unknown property "{key}"')

    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            errors.append(f'{path}: expected at least {schema["minItems"]} items, got {len(value)}')
        item_schema = schema.get('items')
        if item_schema:
            for index, item in enumerate(value):
                validate(item, item_schema, root_schema, f'{path}[{index}]', errors)

    return errors


def load_schema(path):
    return json.load(open(path))

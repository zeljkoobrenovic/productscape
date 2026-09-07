import json
import os
import re


PRODUCT_BRICK_LAYER_ORDER = [
    'ui',
    'interfaces',
    'worker',
    'stateless-service',
    'service',
    'integration'
]


PRODUCT_BRICK_LAYER_LABELS = {
    'ui': 'UI',
    'interfaces': 'Interfaces',
    'worker': 'Worker',
    'stateless-service': 'Stateless Service',
    'service': 'Service',
    'integration': 'Integration'
}


PRODUCT_BRICK_LAYER_DESCRIPTIONS = {
    'ui': 'User-facing web, mobile, backoffice, and operator experience modules.',
    'interfaces': 'APIs, BFFs, and explicit service boundary interfaces exposed to clients or other systems.',
    'worker': 'Background workers, event consumers, daemons, and asynchronous processing modules.',
    'stateless-service': 'Stateless orchestration services that aggregate other services without owning durable state.',
    'service': 'Stateful services and domain service modules that own behavior, policy, workflow, data, or operations.',
    'integration': 'Connectors, adapters, and integration modules for external systems, devices, or partner platforms.'
}


PRODUCT_BRICK_LAYER_HOSTS_MODULES = {
    'ui': ['web-component', 'mobile-component'],
    'interfaces': ['bff', 'api', 'backoffice-interface'],
    'worker': ['message-queue', 'message-consumer', 'daemon'],
    'stateless-service': ['stateless-service'],
    'service': ['stateful-service', 'service'],
    'integration': ['integration']
}


PRODUCT_BRICK_MODULE_TYPE_DESCRIPTIONS = {
    'web-component': 'A browser-based user interface module.',
    'mobile-component': 'A mobile application user interface module.',
    'bff': 'A backend-for-frontend module that shapes APIs for a specific client experience.',
    'api': 'A programmatic API module exposed to product clients, partners, or other systems.',
    'backoffice-interface': 'An internal operations or administration interface module.',
    'message-queue': 'A queue module used for asynchronous communication between modules or systems.',
    'message-consumer': 'A consumer module that processes messages or events in the worker layer.',
    'daemon': 'A background worker or daemon module.',
    'stateless-service': 'A service module that orchestrates work without owning durable state.',
    'stateful-service': 'A service module that owns or manages persistent state, such as a database, stored domain data, or durable business records.',
    'service': 'A domain or platform service module; prefer stateful-service or stateless-service for new modules when the state boundary is known.',
    'integration': 'A connector or adapter module for an external system, partner, device, or platform.'
}


PRODUCT_BRICK_MODULE_TYPE_COLORS = {
    'web-component': '#dbeafe',
    'mobile-component': '#ede9fe',
    'bff': '#fef3c7',
    'api': '#e0f2fe',
    'backoffice-interface': '#fce7f3',
    'message-queue': '#ffedd5',
    'message-consumer': '#fef9c3',
    'daemon': '#e5e7eb',
    'stateless-service': '#ccfbf1',
    'stateful-service': '#dcfce7',
    'service': '#d1fae5',
    'integration': '#fae8ff'
}


def default_modules_config():
    module_type_ids = []
    seen_module_type_ids = set()
    for layer_id in PRODUCT_BRICK_LAYER_ORDER:
        for module_type_id in PRODUCT_BRICK_LAYER_HOSTS_MODULES.get(layer_id, []):
            if module_type_id in seen_module_type_ids:
                continue
            seen_module_type_ids.add(module_type_id)
            module_type_ids.append(module_type_id)

    return {
        'layerTypes': [
            {
                'id': layer_id,
                'name': product_brick_layer_label(layer_id).lower(),
                'description': product_brick_layer_description(layer_id),
                'hostsModules': list(PRODUCT_BRICK_LAYER_HOSTS_MODULES.get(layer_id, []))
            }
            for layer_id in PRODUCT_BRICK_LAYER_ORDER
        ],
        'moduleTypes': [
            {
                'id': module_type_id,
                'name': module_type_id.replace('_', ' ').replace('-', ' '),
                'description': PRODUCT_BRICK_MODULE_TYPE_DESCRIPTIONS.get(
                    module_type_id,
                    f"A {module_type_id.replace('_', ' ').replace('-', ' ')} module used in product-brick architecture models."
                ),
                'color': PRODUCT_BRICK_MODULE_TYPE_COLORS.get(module_type_id, '#f3f4f6')
            }
            for module_type_id in module_type_ids
        ]
    }


UI_MODULE_TYPES = {
    'mobile-component',
    'web-component',
    'ui',
    'web',
    'mobile',
    'mobile_app'
}


INTERFACE_MODULE_TYPES = {
    'bff',
    'api',
    'backoffice-interface'
}


WORKER_MODULE_TYPES = {
    'message-queue',
    'message-consumer',
    'daemon',
    'event'
}


STATELESS_SERVICE_MODULE_TYPES = {
    'stateless-service'
}


SERVICE_MODULE_TYPES = {
    'stateful-service',
    'service'
}


INTEGRATION_MODULE_TYPES = {
    'integration',
    'device',
    'network'
}


ALLOWED_PRODUCT_BRICK_MODULE_TYPES = {
    module_type_id
    for module_type_ids in PRODUCT_BRICK_LAYER_HOSTS_MODULES.values()
    for module_type_id in module_type_ids
}


def slugify(text):
    value = (text or '').strip().lower()
    chars = []
    last_dash = False
    for ch in value:
        if ch.isalnum():
            chars.append(ch)
            last_dash = False
        elif not last_dash:
            chars.append('-')
            last_dash = True
    return ''.join(chars).strip('-')


def product_brick_module_id(value):
    module_slug = slugify(value)
    if module_slug.startswith('module-'):
        return module_slug
    return 'module-' + (module_slug or 'module')


def product_brick_generated_id(brick):
    return slugify((brick or {}).get('name') or (brick or {}).get('title') or 'brick') or 'brick'


def normalize_product_brick_rendering(metadata, root_groups, path=''):
    normalized_metadata = dict(metadata or {})
    rendering = dict(
        normalized_metadata.get('rendering')
        or normalized_metadata.get('render')
        or normalized_metadata.get('renderding')
        or {}
    )

    root_group_names = [group.get('name', '') for group in root_groups or [] if group.get('name')]
    root_group_name_lookup = {name: name for name in root_group_names}
    root_group_slug_lookup = {slugify(name): name for name in root_group_names}

    normalized_rows = []
    for row_info in rendering.get('rows', []) or []:
        normalized_row = dict(row_info)
        configured_names = (
            row_info.get('rootGroupNames')
            or row_info.get('groupNames')
            or row_info.get('brickIds')
            or []
        )
        resolved_names = []
        for configured_name in configured_names:
            resolved_name = root_group_name_lookup.get(configured_name)
            if not resolved_name:
                resolved_name = root_group_slug_lookup.get(slugify(configured_name))
            if not resolved_name:
                details = f" in {path}" if path else ''
                raise ValueError(
                    f"Unknown root group '{configured_name}' referenced by metadata.rendering.rows{details}. "
                    f"Expected one of: {', '.join(root_group_names)}"
                )
            resolved_names.append(resolved_name)

        normalized_row.pop('brickIds', None)
        normalized_row.pop('groupNames', None)
        normalized_row['rootGroupNames'] = resolved_names
        normalized_rows.append(normalized_row)

    if rendering or 'rendering' in normalized_metadata or 'render' in normalized_metadata or 'renderding' in normalized_metadata:
        rendering['rows'] = normalized_rows
        normalized_metadata['rendering'] = rendering

    normalized_metadata.pop('render', None)
    normalized_metadata.pop('renderding', None)
    return normalized_metadata


def normalize_product_brick_metadata(metadata, root_groups, path=''):
    metadata = normalize_product_brick_rendering(dict(metadata or {}), root_groups, path)

    if 'brickTypes' not in metadata and 'types' in metadata:
        metadata['brickTypes'] = metadata.get('types', [])
    if 'brickStatuses' not in metadata and 'statuses' in metadata:
        metadata['brickStatuses'] = metadata.get('statuses', [])
    metadata.pop('types', None)
    metadata.pop('statuses', None)

    metadata['modulesConfig'] = default_modules_config()

    ordered_metadata = {}
    for key in ('title', 'description', 'rendering', 'brickTypes', 'brickStatuses', 'modulesConfig'):
        if key in metadata:
            ordered_metadata[key] = metadata[key]
    for key, value in metadata.items():
        if key not in ordered_metadata:
            ordered_metadata[key] = value
    return ordered_metadata


def product_brick_module_layer_id(module, source_field=''):
    module_type = str((module or {}).get('type', '')).strip().lower()

    if module_type in UI_MODULE_TYPES:
        return 'ui'
    if module_type in INTERFACE_MODULE_TYPES:
        return 'interfaces'
    if module_type in WORKER_MODULE_TYPES:
        return 'worker'
    if module_type in STATELESS_SERVICE_MODULE_TYPES:
        return 'stateless-service'
    if module_type in SERVICE_MODULE_TYPES:
        return 'service'
    if module_type in INTEGRATION_MODULE_TYPES:
        return 'integration'

    # Older domain files used many domain-specific labels for service-shaped modules
    # such as analytics, policy, governance, finance, workflow, and runtime.
    if source_field == 'interfaces':
        return 'interfaces'
    return 'service'


def canonical_product_brick_module_type(module, layer_id):
    module_type = str((module or {}).get('type', '')).strip().lower()
    module_name = str((module or {}).get('name') or (module or {}).get('title') or '').strip().lower()
    module_text = ' '.join([module_type, module_name])

    if module_type in ALLOWED_PRODUCT_BRICK_MODULE_TYPES:
        return module_type
    if layer_id == 'ui':
        if 'mobile' in module_text or 'app' in module_text:
            return 'mobile-component'
        return 'web-component'
    if layer_id == 'interfaces':
        if 'backoffice' in module_text or 'operator' in module_text or 'admin' in module_text:
            return 'backoffice-interface'
        if 'bff' in module_text:
            return 'bff'
        return 'api'
    if layer_id == 'worker':
        if 'queue' in module_text or 'broker' in module_text:
            return 'message-queue'
        if 'daemon' in module_text or 'worker' in module_text or 'job' in module_text:
            return 'daemon'
        return 'message-consumer'
    if layer_id == 'stateless-service':
        return 'stateless-service'
    if layer_id == 'integration':
        return 'integration'
    return 'service'


def product_brick_layer_label(layer_id):
    if layer_id == 'bus':
        layer_id = 'worker'
    return PRODUCT_BRICK_LAYER_LABELS.get(layer_id, str(layer_id or '').replace('-', ' ').title())


def product_brick_layer_description(layer_id):
    if layer_id == 'bus':
        layer_id = 'worker'
    return PRODUCT_BRICK_LAYER_DESCRIPTIONS.get(layer_id, '')


def _module_name(module, fallback):
    if isinstance(module, dict):
        for key in ('title', 'name', 'id'):
            value = str(module.get(key, '')).strip()
            if value:
                return value
    return str(fallback or 'module').strip() or 'module'


def _ensure_layer(layers, layer_id, layer_metadata=None):
    if layer_id not in layers:
        layer_info = dict(layer_metadata or {})
        if 'description' not in layer_info:
            layer_info['description'] = product_brick_layer_description(layer_id)
        layer_info['modules'] = {}
        layers[layer_id] = layer_info
    elif layer_metadata:
        for key, value in layer_metadata.items():
            if key not in ('layer', 'modules') and key not in layers[layer_id]:
                layers[layer_id][key] = value
    return layers[layer_id]


def _add_module_to_layers(layers, module, source_field='', fallback_name='', source_layer_id=''):
    if not module:
        return

    if isinstance(module, dict):
        module_info = dict(module)
    else:
        module_info = {'title': str(module), 'type': ''}

    nested_modules = module_info.pop('internalModules', []) or []
    layer_id = source_layer_id or product_brick_module_layer_id(module_info, source_field)
    if layer_id == 'bus':
        layer_id = 'worker'
    module_name = _module_name(module_info, fallback_name)
    module_info['type'] = canonical_product_brick_module_type(module_info, layer_id)
    if module_info.get('title') == module_name and not module_info.get('name'):
        module_info.pop('title', None)
    if not module_info.get('name'):
        module_info['name'] = module_name
    module_info = {
        'name': module_info.get('name', module_name),
        **{key: value for key, value in module_info.items() if key != 'name'}
    }

    layer = _ensure_layer(layers, layer_id)
    modules = layer.setdefault('modules', {})
    module_key = module_name
    if module_key in modules and modules[module_key] != module_info:
        suffix = 2
        while f'{module_name} {suffix}' in modules:
            suffix += 1
        module_key = f'{module_name} {suffix}'
    modules[module_key] = module_info

    for index, nested_module in enumerate(nested_modules):
        nested_name = _module_name(nested_module, f'{module_name} module {index + 1}')
        _add_module_to_layers(layers, nested_module, 'internalModules', nested_name)


def _add_existing_layer_modules(layers, layer_id, layer_config):
    if not isinstance(layer_config, dict):
        return

    layer_metadata = {key: value for key, value in layer_config.items() if key not in ('layer', 'modules')}
    _ensure_layer(layers, layer_id, layer_metadata)
    modules = layer_config.get('modules', {})

    if isinstance(modules, dict):
        for module_name, module in modules.items():
            if isinstance(module, dict):
                module_info = dict(module)
            else:
                module_info = {'title': str(module), 'type': ''}
            _add_module_to_layers(layers, module_info, 'layers', module_name, layer_id)
        return

    if isinstance(modules, list):
        for index, module in enumerate(modules):
            _add_module_to_layers(layers, module, 'layers', f'{layer_id} module {index + 1}', layer_id)


def compact_product_brick_layers(layers):
    ordered_layers = []
    ordered_keys = list(PRODUCT_BRICK_LAYER_ORDER)
    ordered_keys.extend(key for key in layers.keys() if key not in PRODUCT_BRICK_LAYER_ORDER)
    used_module_ids = set()

    for layer_id in ordered_keys:
        layer_config = layers.get(layer_id)
        if not isinstance(layer_config, dict):
            continue
        modules = layer_config.get('modules', {})
        if not modules:
            continue
        ordered_layer = {'layer': layer_id}
        for key, value in layer_config.items():
            if key != 'modules' and value:
                ordered_layer[key] = value
        ordered_modules = []
        for module in modules.values():
            module_info = dict(module or {})
            base_module_id = product_brick_module_id(module_info.get('id') or module_info.get('name') or 'module')
            module_id = base_module_id
            suffix = 2
            while module_id in used_module_ids:
                module_id = f'{base_module_id}-{suffix}'
                suffix += 1
            used_module_ids.add(module_id)

            ordered_module = {'id': module_id}
            for key in ('name', 'type', 'description', 'data', 'dependencies'):
                if key in module_info:
                    ordered_module[key] = module_info[key]
            for key, value in module_info.items():
                if key not in ordered_module and key != 'id':
                    ordered_module[key] = value
            ordered_modules.append(ordered_module)

        ordered_layer['modules'] = ordered_modules
        ordered_layers.append(ordered_layer)

    return ordered_layers


def normalize_brick_layers(brick):
    layers = {}
    existing_layers = brick.get('layers', {}) if isinstance(brick, dict) else {}

    if isinstance(existing_layers, dict) and existing_layers:
        for layer_id in PRODUCT_BRICK_LAYER_ORDER:
            if layer_id in existing_layers:
                _add_existing_layer_modules(layers, layer_id, existing_layers[layer_id])
        for layer_id, layer_config in existing_layers.items():
            if layer_id not in PRODUCT_BRICK_LAYER_ORDER:
                _add_existing_layer_modules(layers, layer_id, layer_config)
        return compact_product_brick_layers(layers)

    if isinstance(existing_layers, list) and existing_layers:
        layer_items = [
            item for item in existing_layers
            if isinstance(item, dict) and item.get('layer')
        ]
        layer_items.sort(key=lambda item: (
            PRODUCT_BRICK_LAYER_ORDER.index(item.get('layer'))
            if item.get('layer') in PRODUCT_BRICK_LAYER_ORDER
            else len(PRODUCT_BRICK_LAYER_ORDER),
            item.get('layer', '')
        ))
        for layer_config in layer_items:
            _add_existing_layer_modules(layers, layer_config.get('layer'), layer_config)
        return compact_product_brick_layers(layers)

    for index, module in enumerate((brick or {}).get('interfaces', []) or []):
        _add_module_to_layers(layers, module, 'interfaces', f'interface {index + 1}')
    for index, module in enumerate((brick or {}).get('internalModules', []) or []):
        _add_module_to_layers(layers, module, 'internalModules', f'module {index + 1}')

    return compact_product_brick_layers(layers)


def normalize_product_brick(brick):
    if not isinstance(brick, dict):
        return brick

    layers = normalize_brick_layers(brick)
    normalized_brick = {}
    inserted_id = False
    inserted_layers = False
    brick_id = str(brick.get('id', '')).strip()

    for key, value in brick.items():
        if key == 'id':
            normalized_brick['id'] = brick_id or product_brick_generated_id(brick)
            inserted_id = True
            continue
        if key in ('interfaces', 'internalModules', 'layers'):
            if layers and not inserted_layers:
                normalized_brick['layers'] = layers
                inserted_layers = True
            continue
        normalized_brick[key] = value

    if not inserted_id:
        normalized_brick = {'id': product_brick_generated_id(brick), **normalized_brick}

    if layers and not inserted_layers:
        normalized_brick['layers'] = layers

    return normalized_brick


def normalize_product_brick_group(group):
    if not isinstance(group, dict):
        return group

    normalized_group = dict(group)
    normalized_group['subGroups'] = [
        normalize_product_brick_group(sub_group)
        for sub_group in group.get('subGroups', []) or []
    ]
    normalized_group['bricks'] = [
        normalize_product_brick(brick)
        for brick in group.get('bricks', []) or []
    ]
    return normalized_group


def iter_product_bricks_in_root_groups(root_groups):
    def walk_group(group):
        if not isinstance(group, dict):
            return
        for brick in group.get('bricks', []) or []:
            if isinstance(brick, dict):
                yield brick
        for sub_group in group.get('subGroups', []) or []:
            yield from walk_group(sub_group)

    for root_group in root_groups or []:
        yield from walk_group(root_group)


def product_brick_module_entries(brick):
    entries = []
    for layer in (brick or {}).get('layers', []) or []:
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get('layer', '')).strip()
        for module in layer.get('modules', []) or []:
            if not isinstance(module, dict):
                continue
            module_id = str(module.get('id', '')).strip()
            if not module_id:
                continue
            entries.append({
                'id': module_id,
                'name': str(module.get('name', '')).strip(),
                'type': str(module.get('type', '')).strip(),
                'description': str(module.get('description', '')).strip(),
                'layer': layer_id,
                'module': module
            })
    return entries


def data_dependency_module_priority(dependency):
    role = str((dependency or {}).get('role', '')).strip().lower()
    if role == 'publish':
        return ['worker', 'service', 'stateless-service', 'interfaces', 'integration', 'ui']
    if role in {'own', 'write', 'replicate', 'delete'}:
        return ['service', 'stateless-service', 'worker', 'interfaces', 'integration', 'ui']
    if role in {'query', 'read'}:
        return ['service', 'stateless-service', 'interfaces', 'worker', 'integration', 'ui']
    return ['service', 'stateless-service', 'interfaces', 'worker', 'integration', 'ui']


def select_data_dependency_module_ids(brick, dependency):
    entries = product_brick_module_entries(brick)
    module_ids = {entry['id'] for entry in entries}
    requested_module_ids = dependency.get('moduleIds') or dependency.get('moduleId') or []
    if isinstance(requested_module_ids, str):
        requested_module_ids = [requested_module_ids]
    requested_module_ids = [
        str(module_id).strip()
        for module_id in requested_module_ids
        if str(module_id).strip() in module_ids
    ]
    if requested_module_ids:
        return requested_module_ids

    asset_id = str((dependency or {}).get('assetId', '')).strip()
    explicit_module_ids = []
    for entry in entries:
        module_data = entry.get('module', {}).get('data', [])
        if not isinstance(module_data, list):
            module_data = [module_data]
        for data_item in module_data:
            data_asset_id = data_item.get('assetId') if isinstance(data_item, dict) else data_item
            if str(data_asset_id or '').strip() == asset_id:
                explicit_module_ids.append(entry['id'])
                break
    if explicit_module_ids:
        return explicit_module_ids

    for layer_id in data_dependency_module_priority(dependency):
        layer_module_ids = [entry['id'] for entry in entries if entry.get('layer') == layer_id]
        if layer_module_ids:
            return layer_module_ids
    return [entries[0]['id']] if entries else []


def normalize_data_dependency_item(brick, dependency):
    if not isinstance(dependency, dict):
        return dependency

    normalized_dependency = {}
    if dependency.get('assetId'):
        normalized_dependency['assetId'] = dependency.get('assetId')

    module_ids = select_data_dependency_module_ids(brick, dependency)
    if module_ids:
        normalized_dependency['moduleIds'] = module_ids

    for key in ('role', 'description'):
        if key in dependency:
            normalized_dependency[key] = dependency[key]

    for key, value in dependency.items():
        if key in ('assetId', 'moduleId', 'moduleIds', 'storeId', 'storeIds', 'role', 'description'):
            continue
        normalized_dependency[key] = value

    return normalized_dependency


def normalize_data_dependencies(root_groups):
    for brick in iter_product_bricks_in_root_groups(root_groups):
        if 'dataDependencies' not in brick:
            continue
        brick['dataDependencies'] = [
            normalize_data_dependency_item(brick, dependency)
            for dependency in brick.get('dataDependencies', []) or []
        ]
    return root_groups


def _module_dependency_tokens(value):
    tokens = set()
    for token in re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).split():
        if not token:
            continue
        tokens.add(token)
        if token.endswith('s') and len(token) > 3:
            tokens.add(token[:-1])
    return tokens


def _dependency_text(dependency):
    if not isinstance(dependency, dict):
        return ''
    return ' '.join(
        str(dependency.get(key, '')).strip()
        for key in ('interface', 'moduleId', 'targetModuleId', 'type', 'description')
        if str(dependency.get(key, '')).strip()
    )


def _dependency_has_terms(text, terms):
    text_tokens = _module_dependency_tokens(text)
    for term in terms:
        term_tokens = _module_dependency_tokens(term)
        if term_tokens and term_tokens <= text_tokens:
            return True
    return False


def dependency_layer_priority(dependency, source=False):
    text = _dependency_text(dependency)
    default_priority = (
        ['service', 'stateless-service', 'interfaces', 'worker', 'integration', 'ui']
        if source
        else ['interfaces', 'service', 'stateless-service', 'worker', 'integration', 'ui']
    )
    priority = []

    if _dependency_has_terms(text, ['dashboard', 'workspace', 'portal', 'console', 'screen', 'ui']):
        priority.append('ui')
    if _dependency_has_terms(text, ['api', 'apis', 'bff', 'endpoint', 'gateway', 'rest', 'graphql', 'webhook', 'webhooks', 'import', 'export']):
        priority.append('interfaces')
    if _dependency_has_terms(text, ['event', 'events', 'queue', 'stream', 'feed', 'message', 'messages', 'notification', 'notifications']):
        priority.append('worker')
    if _dependency_has_terms(text, ['connector', 'connectors', 'adapter', 'integration', 'erp', 'saml', 'oidc', 'scim']):
        priority.append('integration')
    if _dependency_has_terms(text, ['orchestration', 'workflow', 'service', 'state', 'ledger', 'policy']):
        priority.append('service')

    for layer_id in default_priority:
        if layer_id not in priority:
            priority.append(layer_id)
    return priority


def select_first_module_id(brick, layer_priority):
    entries = product_brick_module_entries(brick)
    for layer_id in layer_priority:
        for entry in entries:
            if entry.get('layer') == layer_id:
                return entry.get('id', '')
    return entries[0].get('id', '') if entries else ''


def module_entry_score(entry, reference, layer_priority):
    reference_tokens = _module_dependency_tokens(reference)
    if not reference_tokens:
        return 0

    module_text = ' '.join([
        entry.get('id', ''),
        entry.get('name', ''),
        entry.get('type', ''),
        entry.get('description', ''),
        entry.get('layer', '')
    ])
    module_tokens = _module_dependency_tokens(module_text)
    score = len(reference_tokens & module_tokens)

    reference_slug = slugify(reference)
    name_slug = slugify(entry.get('name', ''))
    type_slug = slugify(entry.get('type', ''))
    if reference_slug and (reference_slug == name_slug or reference_slug == entry.get('id', '')):
        score += 50
    elif reference_slug and name_slug and (reference_slug in name_slug or name_slug in reference_slug):
        score += 20
    if type_slug and type_slug in reference_slug:
        score += 8
    if entry.get('layer') in layer_priority:
        score += max(0, len(layer_priority) - layer_priority.index(entry.get('layer')))
    return score


def select_module_id_for_reference(brick, reference, layer_priority):
    reference = str(reference or '').strip()
    entries = product_brick_module_entries(brick)
    if not entries:
        return ''
    if reference:
        normalized_reference_id = product_brick_module_id(reference)
        reference_slug = slugify(reference)
        for entry in entries:
            if entry.get('id') in (reference, normalized_reference_id):
                return entry.get('id', '')
            if slugify(entry.get('name', '')) == reference_slug:
                return entry.get('id', '')

        scored_entries = sorted(
            entries,
            key=lambda entry: (
                -module_entry_score(entry, reference, layer_priority),
                layer_priority.index(entry.get('layer')) if entry.get('layer') in layer_priority else len(layer_priority),
                entry.get('id', '')
            )
        )
        if module_entry_score(scored_entries[0], reference, layer_priority) > 0:
            return scored_entries[0].get('id', '')

    return select_first_module_id(brick, layer_priority)


def normalize_brick_dependency_item(source_brick, dependency, brick_lookup):
    if not isinstance(dependency, dict):
        return dependency

    target_brick_id = str(dependency.get('targetBrickId', '')).strip()
    target_brick = brick_lookup.get(target_brick_id, {})
    target_priority = dependency_layer_priority(dependency, source=False)
    source_priority = dependency_layer_priority(dependency, source=True)

    target_module_id = select_module_id_for_reference(
        target_brick,
        dependency.get('moduleId') or dependency.get('targetModuleId') or dependency.get('interface', ''),
        target_priority
    )
    if not target_module_id and dependency.get('interface'):
        target_module_id = product_brick_module_id(dependency.get('interface'))

    source_module_id = select_module_id_for_reference(
        source_brick,
        dependency.get('sourceModuleId', ''),
        source_priority
    )

    normalized_dependency = {}
    if target_brick_id:
        normalized_dependency['targetBrickId'] = target_brick_id
    if target_module_id:
        normalized_dependency['moduleId'] = target_module_id
    if source_module_id:
        normalized_dependency['sourceModuleId'] = source_module_id

    for key in ('type', 'description'):
        if key in dependency:
            normalized_dependency[key] = dependency[key]

    for key, value in dependency.items():
        if key in ('targetBrickId', 'moduleId', 'targetModuleId', 'sourceModuleId', 'interface', 'type', 'description'):
            continue
        normalized_dependency[key] = value

    return normalized_dependency


def normalize_brick_dependencies(root_groups):
    brick_lookup = {}
    for brick in iter_product_bricks_in_root_groups(root_groups):
        brick_id = str(brick.get('id', '')).strip()
        if brick_id and brick_id not in brick_lookup:
            brick_lookup[brick_id] = brick

    for brick in iter_product_bricks_in_root_groups(root_groups):
        if 'brickDependencies' not in brick:
            continue
        brick['brickDependencies'] = [
            normalize_brick_dependency_item(brick, dependency, brick_lookup)
            for dependency in brick.get('brickDependencies', []) or []
        ]
    return root_groups


def normalize_product_brick_root_groups(root_groups):
    normalized_root_groups = [
        normalize_product_brick_group(group)
        for group in root_groups or []
    ]
    normalize_data_dependencies(normalized_root_groups)
    return normalize_brick_dependencies(normalized_root_groups)


_SHARED_CONFIG_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_config', '_shared')
_shared_model_cache = {}


def _shared_model(filename):
    """Shared enum/definition defaults hoisted out of the per-domain files.
    Domain files may still declare these keys to override the shared model."""
    if filename not in _shared_model_cache:
        shared_path = os.path.join(_SHARED_CONFIG_ROOT, filename)
        _shared_model_cache[filename] = json.load(open(shared_path)) if os.path.exists(shared_path) else {}
    return _shared_model_cache[filename]


def apply_shared_defaults(target, filename, keys):
    for key in keys:
        if key not in target and key in _shared_model(filename):
            target[key] = _shared_model(filename)[key]
    return target


def load_product_bricks_payload(path, default_title='Product Bricks', default_description=''):
    if not os.path.exists(path):
        return {
            'metadata': normalize_product_brick_metadata({'title': default_title, 'description': default_description}, []),
            'rootGroups': []
        }

    payload = json.load(open(path))

    if isinstance(payload, list):
        root_groups = normalize_product_brick_root_groups(payload)
        return {
            'metadata': normalize_product_brick_metadata({'title': default_title, 'description': default_description}, root_groups),
            'rootGroups': root_groups
        }

    root_groups = payload.get('rootGroups', payload.get('bricks', []))
    metadata = normalize_product_brick_metadata(dict(payload.get('metadata', {})), root_groups, path)
    if 'title' not in metadata:
        metadata['title'] = default_title
    if 'description' not in metadata:
        metadata['description'] = default_description
    apply_shared_defaults(metadata, 'product-brick-model.json', ('brickTypes', 'brickStatuses', 'modulesConfig'))

    return {
        'metadata': metadata,
        'rootGroups': normalize_product_brick_root_groups(root_groups)
    }


def product_brick_root_groups(payload):
    return payload.get('rootGroups', payload.get('bricks', []))


def load_product_streams_payload(path, default_title='Product Streams', default_description=''):
    if not os.path.exists(path):
        return {
            'metadata': {'title': default_title, 'description': default_description},
            'rootGroups': []
        }

    payload = json.load(open(path))

    if not isinstance(payload, dict):
        raise ValueError(f'Product streams payload must be an object: {path}')

    metadata = dict(payload.get('metadata', {}))
    if 'title' not in metadata:
        metadata['title'] = default_title
    if 'description' not in metadata:
        metadata['description'] = default_description
    apply_shared_defaults(metadata, 'product-stream-model.json', ('definitions',))

    return {
        'metadata': metadata,
        'rootGroups': payload.get('rootGroups', [])
    }


DATA_ASSET_ROOT_GROUP_DEFINITIONS = {
    'people-accounts-access': {
        'name': 'People, Accounts, and Access Data',
        'description': 'Profiles, accounts, credentials, consent, entitlements, and access records used to identify people and govern their access.'
    },
    'commercial-financial': {
        'name': 'Commercial and Financial Data',
        'description': 'Pricing, payment, billing, subscription, revenue, settlement, ledger, and other commercial records.'
    },
    'product-catalog-content': {
        'name': 'Product, Catalog, and Content Data',
        'description': 'Catalogs, listings, inventory, content, media, products, and merchandising data exposed through customer or operator experiences.'
    },
    'operations-workflow-events': {
        'name': 'Operational Workflow and Event Data',
        'description': 'Orders, bookings, trips, tasks, incidents, service requests, workflow states, and operational events used to run the domain.'
    },
    'risk-governance-security': {
        'name': 'Risk, Governance, Security, and Compliance Data',
        'description': 'Risk signals, safety records, audit trails, policies, controls, approvals, and compliance evidence.'
    },
    'architecture-portfolio-planning': {
        'name': 'Architecture, Portfolio, and Planning Data',
        'description': 'Architecture models, portfolio records, streams, roadmaps, standards, and planning evidence.'
    },
    'analytics-metrics-insights': {
        'name': 'Analytics, Metrics, and Insight Data',
        'description': 'Metrics, telemetry, experiments, measurements, forecasts, recommendations, and derived analytical insight.'
    },
    'integration-platform-technical': {
        'name': 'Integration, Platform, and Technical Data',
        'description': 'API, connector, integration, runtime, infrastructure, configuration, and platform operations data.'
    },
    'reference-master-data': {
        'name': 'Reference and Master Data',
        'description': 'Reusable reference, policy, rule, taxonomy, and master data used to standardize domain behavior.'
    },
    'core-domain-records': {
        'name': 'Core Domain Records',
        'description': 'Primary domain records that do not fit a more specialized data group.'
    }
}


DATA_ASSET_ROOT_GROUP_ORDER = [
    'people-accounts-access',
    'commercial-financial',
    'product-catalog-content',
    'operations-workflow-events',
    'risk-governance-security',
    'architecture-portfolio-planning',
    'analytics-metrics-insights',
    'integration-platform-technical',
    'reference-master-data',
    'core-domain-records'
]


DATA_ASSET_SUBGROUP_DEFINITIONS = {
    'core-records': {
        'name': 'Core Records',
        'description': 'Durable domain entities and business objects.'
    },
    'events-and-logs': {
        'name': 'Events and Logs',
        'description': 'Append-only events, logs, state changes, and operational traces.'
    },
    'financial-records': {
        'name': 'Financial Records',
        'description': 'Commercial, payment, billing, ledger, and settlement records.'
    },
    'analytics-and-derived-data': {
        'name': 'Analytics and Derived Data',
        'description': 'Aggregated, calculated, scored, predicted, or insight-oriented datasets.'
    },
    'reference-and-policy-data': {
        'name': 'Reference and Policy Data',
        'description': 'Reference lists, policies, rules, configuration, and taxonomies.'
    },
    'documents-and-evidence': {
        'name': 'Documents and Evidence',
        'description': 'Documents, media, knowledge, files, and evidence packages.'
    }
}


DATA_ASSET_SUBGROUP_ORDER = [
    'core-records',
    'financial-records',
    'events-and-logs',
    'reference-and-policy-data',
    'documents-and-evidence',
    'analytics-and-derived-data'
]


def _asset_text(asset):
    values = [
        asset.get('id', ''),
        asset.get('name', ''),
        asset.get('kind', ''),
        asset.get('description', ''),
        asset.get('businessMeaning', ''),
        asset.get('ownerTeamId', ''),
        asset.get('systemOfRecordBrickId', ''),
        ' '.join(asset.get('tags', []) or [])
    ]
    return ' '.join(str(value).lower() for value in values if value)


def _asset_identity_text(asset):
    values = [
        asset.get('id', ''),
        asset.get('name', ''),
        asset.get('kind', ''),
        ' '.join(asset.get('tags', []) or [])
    ]
    return ' '.join(str(value).lower() for value in values if value)


def _text_has_any(text, keywords):
    normalized_text = re.sub(r'[^a-z0-9]+', ' ', text or '').strip()
    tokens = set(normalized_text.split())
    for keyword in keywords:
        normalized_keyword = re.sub(r'[^a-z0-9]+', ' ', keyword.lower()).strip()
        if not normalized_keyword:
            continue
        if ' ' in normalized_keyword:
            if normalized_keyword in normalized_text:
                return True
        elif normalized_keyword in tokens:
            return True
    return False


def data_asset_root_group_key(asset):
    text = _asset_text(asset)
    identity_text = _asset_identity_text(asset)
    kind = str(asset.get('kind', '')).lower()

    finance_keywords = [
        'payment', 'transaction', 'ledger', 'invoice', 'billing', 'payout', 'subscription',
        'pricing', 'price', 'quote', 'proposal', 'spend', 'revenue', 'cost', 'budget',
        'costs', 'settlement', 'tariff', 'financial', 'finance', 'commerce', 'commission',
        'rate'
    ]
    product_keywords = [
        'catalog', 'content', 'listing', 'property', 'inventory', 'menu', 'media',
        'article', 'product', 'sku', 'assortment', 'creative',
        'knowledge', 'course', 'playlist', 'episode', 'track', 'classified'
    ]
    operations_keywords = [
        'order', 'booking', 'delivery', 'dispatch', 'trip', 'ride', 'shipment',
        'workflow', 'work-item', 'work item', 'service-request', 'service request',
        'case', 'operation', 'task', 'status', 'event', 'availability', 'assignment',
        'session orchestration', 'charging session', 'fulfillment'
    ]
    risk_keywords = [
        'risk', 'fraud', 'safety', 'security', 'audit', 'governance', 'compliance',
        'control', 'approval', 'permission', 'policy', 'vulnerability', 'incident',
        'evidence', 'entitlement', 'legal'
    ]
    people_keywords = [
        'customer', 'consumer', 'user', 'member', 'employee', 'traveler', 'rider',
        'driver', 'courier', 'merchant account', 'host', 'guest', 'partner account',
        'shipper account', 'carrier profile', 'seller', 'buyer', 'account', 'profile',
        'contact', 'consent', 'identity', 'credential', 'session-token',
        'session token', 'access', 'role', 'tenant'
    ]

    if _text_has_any(text, [
        'architecture', 'relationship', 'application inventory', 'stream',
        'technology standard', 'portfolio', 'roadmap', 'metamodel',
        'standard', 'process model', 'transformation'
    ]):
        return 'architecture-portfolio-planning'
    if _text_has_any(identity_text, finance_keywords):
        return 'commercial-financial'
    if _text_has_any(identity_text, product_keywords):
        return 'product-catalog-content'
    if _text_has_any(identity_text, risk_keywords):
        return 'risk-governance-security'
    if _text_has_any(identity_text, operations_keywords):
        return 'operations-workflow-events'
    if _text_has_any(text, people_keywords):
        return 'people-accounts-access'
    if _text_has_any(text, product_keywords):
        return 'product-catalog-content'
    if _text_has_any(text, operations_keywords):
        return 'operations-workflow-events'
    if _text_has_any(text, finance_keywords):
        return 'commercial-financial'
    if _text_has_any(text, risk_keywords):
        return 'risk-governance-security'
    if _text_has_any(text, [
        'metric', 'analytics', 'insight', 'telemetry', 'experiment', 'score',
        'forecast', 'recommendation', 'measurement', 'report', 'benchmark',
        'statistic', 'propensity', 'signal', 'quality', 'performance'
    ]):
        return 'analytics-metrics-insights'
    if _text_has_any(text, [
        'api', 'integration', 'connector', 'runtime', 'infrastructure', 'cloud',
        'configuration', 'config', 'deployment', 'environment', 'system', 'token',
        'log'
    ]):
        return 'integration-platform-technical'
    if kind == 'reference-data':
        return 'reference-master-data'
    return 'core-domain-records'


def data_asset_subgroup_key(asset):
    text = _asset_identity_text(asset)
    kind = str(asset.get('kind', '')).lower()
    kind_terms = set(re.sub(r'[^a-z0-9]+', ' ', kind).split())

    if 'financial' in kind_terms or _text_has_any(text, [
        'ledger', 'payment', 'billing', 'invoice', 'settlement', 'transaction',
        'payout', 'revenue', 'pricing', 'price', 'quote', 'proposal', 'spend',
        'cost', 'budget', 'tariff'
    ]):
        return 'financial-records'
    if {'event', 'log', 'stream'} & kind_terms or _text_has_any(text, ['event', 'log', 'telemetry', 'stream']):
        return 'events-and-logs'
    if kind == 'reference-data' or _text_has_any(text, ['reference', 'policy', 'rule', 'taxonomy', 'config', 'standard']):
        return 'reference-and-policy-data'
    if 'document' in kind or _text_has_any(text, ['document', 'evidence', 'media', 'content', 'article', 'knowledge', 'file']):
        return 'documents-and-evidence'
    if any(token in kind for token in ['analytics', 'derived', 'metric', 'cache']) or _text_has_any(text, [
        'metric', 'analytics', 'insight', 'score', 'forecast', 'recommendation',
        'measurement', 'report', 'benchmark', 'statistic', 'performance'
    ]):
        return 'analytics-and-derived-data'
    return 'core-records'


def group_data_assets(assets):
    root_index = {}
    sub_index = {}

    for asset in assets or []:
        root_key = data_asset_root_group_key(asset)
        subgroup_key = data_asset_subgroup_key(asset)

        if root_key not in root_index:
            root_info = DATA_ASSET_ROOT_GROUP_DEFINITIONS[root_key]
            root_index[root_key] = {
                'name': root_info['name'],
                'description': root_info['description'],
                'subGroups': []
            }
            sub_index[root_key] = {}

        if subgroup_key not in sub_index[root_key]:
            subgroup_info = DATA_ASSET_SUBGROUP_DEFINITIONS[subgroup_key]
            subgroup = {
                'name': subgroup_info['name'],
                'description': subgroup_info['description'],
                'assets': []
            }
            sub_index[root_key][subgroup_key] = subgroup
            root_index[root_key]['subGroups'].append(subgroup)

        sub_index[root_key][subgroup_key]['assets'].append(asset)

    def root_order(item):
        key, _ = item
        return DATA_ASSET_ROOT_GROUP_ORDER.index(key) if key in DATA_ASSET_ROOT_GROUP_ORDER else len(DATA_ASSET_ROOT_GROUP_ORDER)

    def subgroup_order(subgroup):
        name = subgroup.get('name', '')
        for key in DATA_ASSET_SUBGROUP_ORDER:
            if DATA_ASSET_SUBGROUP_DEFINITIONS[key]['name'] == name:
                return DATA_ASSET_SUBGROUP_ORDER.index(key)
        return len(DATA_ASSET_SUBGROUP_ORDER)

    groups = []
    for root_key, root_group in sorted(root_index.items(), key=root_order):
        root_group['subGroups'] = sorted(root_group.get('subGroups', []), key=subgroup_order)
        groups.append(root_group)
    return groups


def flatten_data_asset_groups(groups):
    assets = []

    def walk(group):
        assets.extend(group.get('assets', []) or [])
        for subgroup in group.get('subGroups', []) or []:
            walk(subgroup)

    for group in groups or []:
        walk(group)
    return assets


def load_data_assets_payload(path, default_title='Data Assets', default_description=''):
    if not os.path.exists(path):
        return {
            'metadata': {'title': default_title, 'description': default_description},
            'rootGroups': [],
            'assets': [],
            'stores': []
        }

    payload = json.load(open(path))
    metadata = dict(payload.get('metadata', {}))
    if 'title' not in metadata:
        metadata['title'] = default_title
    if 'description' not in metadata:
        metadata['description'] = default_description
    root_groups = payload.get('rootGroups') or payload.get('assetGroups') or payload.get('dataAssetGroups') or []
    assets = payload.get('assets') or flatten_data_asset_groups(root_groups)
    if assets and not root_groups:
        root_groups = group_data_assets(assets)

    return {
        'metadata': metadata,
        'rootGroups': root_groups,
        'assets': assets,
        'stores': payload.get('stores', [])
    }


def product_stream_root_groups(payload):
    return payload.get('rootGroups', [])


def sanitize_stream_flows(flows):
    sanitized_flows = []
    for flow in flows or []:
        sanitized_flow = dict(flow)
        sanitized_steps = []
        for step in flow.get('steps', []) or []:
            sanitized_step = dict(step)
            sanitized_step['dependencies'] = [
                dependency for dependency in step.get('dependencies', [])
                if dependency.get('type', 'brick') == 'brick'
            ]
            sanitized_steps.append(sanitized_step)
        sanitized_flow['steps'] = sanitized_steps
        sanitized_flows.append(sanitized_flow)
    return sanitized_flows


def flatten_product_bricks(payload):
    flat_bricks = []

    def walk_group(group, ancestors):
        next_ancestors = ancestors + [group]
        for sub_group in group.get('subGroups', []):
            walk_group(sub_group, next_ancestors)

        domain_name = next_ancestors[0].get('name', '') if next_ancestors else ''
        group_name = next_ancestors[-1].get('name', '') if next_ancestors else ''

        for node in group.get('bricks', []):
            flat_bricks.append({
                'id': node.get('id', ''),
                'name': node.get('name', ''),
                'type': node.get('type', ''),
                'status': node.get('status', ''),
                'description': node.get('description', ''),
                'links': node.get('links', []),
                'layers': normalize_brick_layers(node),
                'dataDependencies': node.get('dataDependencies', []),
                'brickDependencies': node.get('brickDependencies', []),
                'externalSystemsThisBrickDependsOn': node.get('externalSystemsThisBrickDependsOn', node.get('externalSystemDependencies', [])),
                'externalSystemsDependingOnThisBrick': node.get('externalSystemsDependingOnThisBrick', []),
                'domain': domain_name,
                'group': group_name
            })

    for group in product_brick_root_groups(payload):
        walk_group(group, [])

    return flat_bricks


def flatten_product_streams(payload):
    flat_streams = []

    def walk_group(group, ancestors):
        next_ancestors = ancestors + [group]
        for sub_group in group.get('subGroups', []):
            walk_group(sub_group, next_ancestors)

        root_group_name = next_ancestors[0].get('name', '') if next_ancestors else ''
        group_name = next_ancestors[-1].get('name', '') if next_ancestors else ''

        for stream in group.get('streams', []):
            flat_streams.append({
                'id': stream.get('id', ''),
                'name': stream.get('name', ''),
                'icon': stream.get('icon', str(stream.get('id', '')) + '.png'),
                'type': stream.get('type', 'outcome-based-stream'),
                'description': stream.get('description', ''),
                'group': stream.get('group', group_name),
                'rootGroup': stream.get('rootGroup', root_group_name),
                'flows': sanitize_stream_flows(stream.get('flows', [])),
                'outcomes': stream.get('outcomes', []),
                'brickDependencies': stream.get('brickDependencies', stream.get('productBrickDependencies', [])),
                'externalSystemsThisStreamDependsOn': stream.get('externalSystemsThisStreamDependsOn', []),
                'externalSystemsDependingOnThisStream': stream.get('externalSystemsDependingOnThisStream', []),
                'owningTeams': stream.get('owningTeams', [])
            })

    for group in product_stream_root_groups(payload):
        walk_group(group, [])

    return flat_streams


def sanitize_product_stream_root_groups(groups, ancestors=None):
    sanitized_groups = []
    ancestors = ancestors or []

    for group in groups or []:
        next_ancestors = ancestors + [group]
        root_group_name = next_ancestors[0].get('name', '') if next_ancestors else ''
        group_name = next_ancestors[-1].get('name', '') if next_ancestors else ''

        sanitized_groups.append({
            'name': group.get('name', ''),
            'description': group.get('description', ''),
            'subGroups': sanitize_product_stream_root_groups(group.get('subGroups', []), next_ancestors),
            'streams': [
                {
                    'id': stream.get('id', ''),
                    'name': stream.get('name', ''),
                    'icon': stream.get('icon', str(stream.get('id', '')) + '.png'),
                    'type': stream.get('type', 'outcome-based-stream'),
                    'description': stream.get('description', ''),
                    'group': stream.get('group', group_name),
                    'rootGroup': stream.get('rootGroup', root_group_name),
                    'flows': sanitize_stream_flows(stream.get('flows', [])),
                    'outcomes': stream.get('outcomes', []),
                    'brickDependencies': stream.get('brickDependencies', stream.get('productBrickDependencies', [])),
                    'externalSystemsThisStreamDependsOn': stream.get('externalSystemsThisStreamDependsOn', []),
                    'externalSystemsDependingOnThisStream': stream.get('externalSystemsDependingOnThisStream', []),
                    'owningTeams': stream.get('owningTeams', [])
                }
                for stream in group.get('streams', [])
            ]
        })

    return sanitized_groups


def build_bricks_lookup(product_bricks_payload):
    lookup = {}
    for item in flatten_product_bricks(product_bricks_payload):
        lookup[str(item['id'])] = {
            'id': str(item['id']),
            'name': item.get('name', str(item['id'])),
            'type': item.get('type', ''),
            'status': item.get('status', ''),
            'description': item.get('description', ''),
            'links': item.get('links', []),
            'domain': item.get('domain', ''),
            'group': item.get('group', ''),
            'layers': item.get('layers', {}),
            'dataDependencies': item.get('dataDependencies', []),
            'brickDependencies': item.get('brickDependencies', []),
            'externalSystemsThisBrickDependsOn': item.get('externalSystemsThisBrickDependsOn', item.get('externalSystemDependencies', [])),
            'externalSystemsDependingOnThisBrick': item.get('externalSystemsDependingOnThisBrick', []),
            'icon': str(item['id']) + '.png'
        }
    return lookup


def legacy_bricks_to_payload(items, title='Product Bricks', description=''):
    domains = []
    domain_index = {}

    for item in items:
        domain_name = item.get('domain', 'Other')
        group_name = item.get('group', 'Ungrouped')

        if domain_name not in domain_index:
            domain_node = {
                'id': slugify(domain_name) or 'group',
                'name': domain_name,
                'type': 'group',
                'description': '',
                'children': []
            }
            domain_index[domain_name] = {
                'node': domain_node,
                'groups': {}
            }
            domains.append(domain_node)

        domain_entry = domain_index[domain_name]

        if group_name not in domain_entry['groups']:
            group_node = {
                'id': slugify(domain_name + ' ' + group_name) or slugify(group_name) or 'group',
                'name': group_name,
                'type': 'group',
                'description': '',
                'children': []
            }
            domain_entry['groups'][group_name] = group_node
            domain_entry['node']['children'].append(group_node)

        domain_entry['groups'][group_name]['children'].append({
            'id': item.get('id', ''),
            'name': item.get('name', ''),
            'type': item.get('type', ''),
            'description': item.get('description', ''),
            'links': item.get('links', []),
            'layers': normalize_brick_layers(item),
            'dataDependencies': item.get('dataDependencies', []),
            'brickDependencies': item.get('brickDependencies', []),
            'externalSystemsThisBrickDependsOn': item.get('externalSystemsThisBrickDependsOn', item.get('externalSystemDependencies', [])),
            'externalSystemsDependingOnThisBrick': item.get('externalSystemsDependingOnThisBrick', []),
            'children': []
        })

    return {
        'metadata': {
            'title': title,
            'description': description
        },
        'rootGroups': [
            {
                'name': domain.get('name', ''),
                'description': domain.get('description', ''),
                'subGroups': [
                    {
                        'name': group.get('name', ''),
                        'description': group.get('description', ''),
                        'subGroups': [],
                        'bricks': [
                            {
                                'id': child.get('id', ''),
                                'name': child.get('name', ''),
                                'type': child.get('type', ''),
                                'description': child.get('description', ''),
                                'links': child.get('links', []),
                                'layers': normalize_brick_layers(child),
                                'dataDependencies': child.get('dataDependencies', []),
                                'brickDependencies': child.get('brickDependencies', []),
                                'externalSystemsThisBrickDependsOn': child.get('externalSystemsThisBrickDependsOn', child.get('externalSystemDependencies', [])),
                                'externalSystemsDependingOnThisBrick': child.get('externalSystemsDependingOnThisBrick', [])
                            }
                            for child in group.get('children', [])
                        ]
                    }
                    for group in domain.get('children', [])
                ],
                'bricks': []
            }
            for domain in domains
        ]
    }

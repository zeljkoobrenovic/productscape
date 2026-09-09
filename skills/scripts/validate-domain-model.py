#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / '_wiring'))
from domain_paths import discover_domain_dirs, resolve_domain_dir

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_check
from tutorial_model import validate_tutorial

# artifact path (relative to the domain folder) -> schema file in _config/_schema/
SCHEMA_BY_ARTIFACT = {
    'start/config.json': 'config.schema.json',
    'customers/customers.json': 'customers.schema.json',
    'customers/insights.json': 'insights.schema.json',
    'customers/links.json': 'links.schema.json',
    'product-deployments/products.json': 'products.schema.json',
    'product-deployments/deployment.json': 'deployment.schema.json',
    'product-bricks/product-bricks.json': 'product-bricks.schema.json',
    'product-bricks/product-stream.json': 'product-stream.schema.json',
    'teams/teams.json': 'teams.schema.json',
    'data/data-assets.json': 'data-assets.schema.json',
    'business/competition.json': 'competition.schema.json',
    'residuality/residuality.json': 'residuality.schema.json',
    'tutorial/tutorial.json': 'tutorial.schema.json',
}
_schema_cache = {}


def validate_against_schema(domain_dir, json_path, payload, errors):
    relative = json_path.relative_to(domain_dir).as_posix()
    schema_name = SCHEMA_BY_ARTIFACT.get(relative)
    if not schema_name:
        return
    if relative == 'tutorial/tutorial.json':
        for problem in validate_tutorial(payload, domain_dir.name, domain_dir / 'tutorial'):
            errors.append(f'{domain_dir.name}: {relative} {problem}')
        return
    if schema_name not in _schema_cache:
        schema_path = REPO_ROOT / '_config' / '_schema' / schema_name
        if not schema_path.exists():
            return
        _schema_cache[schema_name] = schema_check.load_schema(schema_path)
    for problem in schema_check.validate(payload, _schema_cache[schema_name]):
        errors.append(f'{domain_dir.name}: {relative} {problem}')


LOWER_ID_RE = re.compile(r'^[a-z0-9][a-z0-9._:-]*$')
PRODUCT_BRICK_LAYER_IDS = {'ui', 'interfaces', 'worker', 'stateless-service', 'service', 'integration'}
PRODUCT_BRICK_MODULE_TYPES = {
    'web-component',
    'mobile-component',
    'bff',
    'api',
    'backoffice-interface',
    'message-queue',
    'message-consumer',
    'daemon',
    'stateless-service',
    'stateful-service',
    'service',
    'integration',
}


def load_json(path, errors):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        errors.append(f'{path}: invalid JSON: {exc}')
        return None


def collect_bricks(payload):
    bricks = {}

    def walk(node):
        if isinstance(node, dict):
            for brick in node.get('bricks', []) or []:
                if isinstance(brick, dict) and brick.get('id'):
                    brick_id = str(brick.get('id')).strip()
                    bricks.setdefault(brick_id, []).append(brick.get('name', brick_id))
            for key in ('rootGroups', 'subGroups'):
                for child in node.get(key, []) or []:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload.get('rootGroups', []) if isinstance(payload, dict) else payload)
    return bricks


def iter_product_bricks(payload):
    def walk(node):
        if isinstance(node, dict):
            for brick in node.get('bricks', []) or []:
                if isinstance(brick, dict):
                    yield brick
            for key in ('rootGroups', 'subGroups'):
                for child in node.get(key, []) or []:
                    yield from walk(child)
        elif isinstance(node, list):
            for child in node:
                yield from walk(child)

    yield from walk(payload.get('rootGroups', []) if isinstance(payload, dict) else payload)


def module_ids_for_brick(brick):
    module_ids = set()
    for layer in brick.get('layers', []) or []:
        if not isinstance(layer, dict):
            continue
        for module in layer.get('modules', []) or []:
            if isinstance(module, dict) and module.get('id'):
                module_ids.add(str(module.get('id')).strip())
    return module_ids


def module_dependency_id(dependency):
    if isinstance(dependency, dict):
        return str(
            dependency.get('moduleId')
            or dependency.get('targetModuleId')
            or dependency.get('id')
            or dependency.get('module')
            or dependency.get('target')
            or ''
        ).strip()
    return str(dependency or '').strip()


def validate_product_bricks_model(domain_dir, payload, errors):
    metadata = payload.get('metadata', {}) if isinstance(payload, dict) else {}
    modules_config = metadata.get('modulesConfig', {}) if isinstance(metadata, dict) else {}
    layer_type_ids = {item.get('id') for item in modules_config.get('layerTypes', []) or [] if isinstance(item, dict)}
    module_type_ids = {item.get('id') for item in modules_config.get('moduleTypes', []) or [] if isinstance(item, dict)}
    if layer_type_ids and layer_type_ids != PRODUCT_BRICK_LAYER_IDS:
        errors.append(f'{domain_dir.name}: modulesConfig.layerTypes must match the supported product-brick layers')
    if module_type_ids and module_type_ids != PRODUCT_BRICK_MODULE_TYPES:
        errors.append(f'{domain_dir.name}: modulesConfig.moduleTypes must match the supported product-brick module types')
    for module_type in modules_config.get('moduleTypes', []) or []:
        if not isinstance(module_type, dict):
            continue
        module_type_id = module_type.get('id')
        if module_type_id in PRODUCT_BRICK_MODULE_TYPES and not str(module_type.get('color', '')).strip():
            errors.append(f'{domain_dir.name}: modulesConfig.moduleTypes.{module_type_id} is missing color')

    bricks = list(iter_product_bricks(payload))
    brick_lookup = {}
    for brick in bricks:
        brick_id = str(brick.get('id', '')).strip()
        if not brick_id:
            errors.append(f'{domain_dir.name}: product brick without id: {brick.get("name", "<missing-name>")}')
            continue
        if brick_id not in brick_lookup:
            brick_lookup[brick_id] = brick

    for brick in bricks:
        brick_id = str(brick.get('id', '')).strip() or '<missing-id>'
        if 'interfaces' in brick:
            errors.append(f'{domain_dir.name}: brick {brick_id} uses legacy top-level interfaces')
        if 'internalModules' in brick:
            errors.append(f'{domain_dir.name}: brick {brick_id} uses legacy top-level internalModules')

        layers = brick.get('layers', [])
        if layers and not isinstance(layers, list):
            errors.append(f'{domain_dir.name}: brick {brick_id} layers must be an array')
            layers = []

        brick_module_ids = set()
        brick_modules = []
        for layer in layers or []:
            if not isinstance(layer, dict):
                errors.append(f'{domain_dir.name}: brick {brick_id} has non-object layer entry')
                continue
            layer_id = str(layer.get('layer', '')).strip()
            if not layer_id:
                errors.append(f'{domain_dir.name}: brick {brick_id} has layer without layer id')
            elif layer_id not in PRODUCT_BRICK_LAYER_IDS:
                errors.append(f'{domain_dir.name}: brick {brick_id} uses unsupported layer: {layer_id}')
            modules = layer.get('modules', [])
            if modules and not isinstance(modules, list):
                errors.append(f'{domain_dir.name}: brick {brick_id} layer {layer_id or "<missing-layer>"} modules must be an array')
                continue
            for module in modules or []:
                if not isinstance(module, dict):
                    errors.append(f'{domain_dir.name}: brick {brick_id} layer {layer_id or "<missing-layer>"} has non-object module')
                    continue
                module_id = str(module.get('id', '')).strip()
                if not module_id:
                    errors.append(f'{domain_dir.name}: brick {brick_id} has module without id')
                    continue
                if not module_id.startswith('module-'):
                    errors.append(f'{domain_dir.name}: brick {brick_id} module id must start with module-: {module_id}')
                module_type = str(module.get('type', '')).strip()
                if module_type and module_type not in PRODUCT_BRICK_MODULE_TYPES:
                    errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} uses unsupported type: {module_type}')
                if module_id in brick_module_ids:
                    errors.append(f'{domain_dir.name}: brick {brick_id} has duplicate module id: {module_id}')
                brick_module_ids.add(module_id)
                brick_modules.append(module)

        for module in brick_modules:
            module_id = str(module.get('id', '')).strip()
            dependencies = module.get('dependencies', {})
            if not dependencies:
                continue
            if not isinstance(dependencies, dict):
                errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} dependencies must be an object')
                continue
            module_dependencies = dependencies.get('modules', [])
            if isinstance(module_dependencies, (str, dict)):
                module_dependencies = [module_dependencies]
            if module_dependencies and not isinstance(module_dependencies, list):
                errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} dependencies.modules must be an array')
                continue
            for dependency in module_dependencies:
                target_module_id = module_dependency_id(dependency)
                if not target_module_id:
                    errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} dependency is missing moduleId')
                    continue
                if target_module_id == module_id:
                    errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} depends on itself')
                target_brick_id = ''
                if isinstance(dependency, dict):
                    target_brick_id = str(dependency.get('targetBrickId') or dependency.get('brickId') or '').strip()
                if target_brick_id and target_brick_id in brick_lookup:
                    target_module_ids = module_ids_for_brick(brick_lookup[target_brick_id])
                    if target_module_id not in target_module_ids:
                        errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} dependency on {target_brick_id} references missing moduleId: {target_module_id}')
                elif target_module_id not in brick_module_ids:
                    errors.append(f'{domain_dir.name}: brick {brick_id} module {module_id} references missing dependency moduleId: {target_module_id}')

        for dependency in brick.get('brickDependencies', []) or []:
            if not isinstance(dependency, dict):
                continue
            if 'interface' in dependency:
                errors.append(f'{domain_dir.name}: brick {brick_id} dependency uses legacy interface field')
            target_brick_id = str(dependency.get('targetBrickId', '')).strip()
            target_module_id = str(dependency.get('moduleId', '')).strip()
            source_module_id = str(dependency.get('sourceModuleId', '')).strip()
            if target_brick_id and not target_module_id:
                errors.append(f'{domain_dir.name}: brick {brick_id} dependency on {target_brick_id} is missing moduleId')
            if source_module_id and source_module_id not in brick_module_ids:
                errors.append(f'{domain_dir.name}: brick {brick_id} dependency references missing sourceModuleId: {source_module_id}')
            if target_brick_id and target_brick_id in brick_lookup and target_module_id:
                target_module_ids = module_ids_for_brick(brick_lookup[target_brick_id])
                if target_module_id not in target_module_ids:
                    errors.append(f'{domain_dir.name}: brick {brick_id} dependency on {target_brick_id} references missing moduleId: {target_module_id}')

        for data_dependency in brick.get('dataDependencies', []) or []:
            if not isinstance(data_dependency, dict):
                continue
            if 'storeId' in data_dependency or 'storeIds' in data_dependency:
                errors.append(f'{domain_dir.name}: brick {brick_id} data dependency uses legacy storeIds field')
            module_ids = data_dependency.get('moduleIds', [])
            if isinstance(module_ids, str):
                module_ids = [module_ids]
            if data_dependency.get('assetId') and not module_ids:
                errors.append(f'{domain_dir.name}: brick {brick_id} data dependency on {data_dependency.get("assetId")} is missing moduleIds')
            for module_id in module_ids:
                if module_id not in brick_module_ids:
                    errors.append(f'{domain_dir.name}: brick {brick_id} data dependency references missing moduleId: {module_id}')

        for field_name in ('externalSystemsThisBrickDependsOn', 'externalSystemDependencies'):
            for external_dependency in brick.get(field_name, []) or []:
                if not isinstance(external_dependency, dict):
                    continue
                source_module_id = str(
                    external_dependency.get('sourceModuleId')
                    or external_dependency.get('moduleId')
                    or external_dependency.get('module')
                    or ''
                ).strip()
                if not source_module_id:
                    errors.append(f'{domain_dir.name}: brick {brick_id} {field_name} entry is missing sourceModuleId')
                    continue
                if source_module_id not in brick_module_ids:
                    errors.append(f'{domain_dir.name}: brick {brick_id} {field_name} references missing sourceModuleId: {source_module_id}')

        for external_dependency in brick.get('externalSystemsDependingOnThisBrick', []) or []:
            if not isinstance(external_dependency, dict):
                continue
            target_module_id = str(
                external_dependency.get('moduleId')
                or external_dependency.get('targetModuleId')
                or external_dependency.get('module')
                or ''
            ).strip()
            if not target_module_id:
                errors.append(f'{domain_dir.name}: brick {brick_id} externalSystemsDependingOnThisBrick entry is missing moduleId')
                continue
            if target_module_id not in brick_module_ids:
                errors.append(f'{domain_dir.name}: brick {brick_id} externalSystemsDependingOnThisBrick references missing moduleId: {target_module_id}')


def iter_id_values(node, path=''):
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f'{path}.{key}' if path else key
            if key == 'id' or key.endswith('Id') or key.endswith('Ids') or key == 'objectId':
                if isinstance(value, str):
                    yield child_path, value
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        if isinstance(item, str):
                            yield f'{child_path}[{index}]', item
            yield from iter_id_values(value, child_path)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from iter_id_values(item, f'{path}[{index}]')


def validate_lowercase_ids(domain_dir, payload, errors, composite_targets=False):
    for field_path, value in iter_id_values(payload):
        if 'evidence-ids' in field_path or field_path.endswith('keyResultId'):
            continue
        if value and value != value.lower():
            errors.append(f'{domain_dir.name}: {field_path} is not lowercase: {value}')
        parts = value.split('/') if composite_targets and re.fullmatch(
            r'stressors\[\d+\]\.impacts\[\d+\]\.targetId', field_path
        ) else [value]
        if value and not all(LOWER_ID_RE.fullmatch(part) for part in parts):
            errors.append(f'{domain_dir.name}: {field_path} has unexpected ID characters: {value}')


def brick_ref_id(ref):
    if not isinstance(ref, dict):
        return ''
    return str(ref.get('brickId') or ref.get('objectId') or '').strip()


def iter_team_groups(groups):
    """Yield every (group, team) pair across the recursive group tree."""
    for group in groups or []:
        for team in group.get('teams', []) or []:
            yield group, team
        for pair in iter_team_groups(group.get('groups', [])):
            yield pair


def validate_team_model(domain_dir, bricks, errors):
    teams_path = domain_dir / 'teams' / 'teams.json'
    if not teams_path.exists():
        return

    payload = load_json(teams_path, errors)
    if payload is None:
        return

    org_design = dict(payload.get('orgDesign', {})) if isinstance(payload, dict) else {}
    # shared enum fallback: domains may omit teamTypes/teamDependencyTypes and
    # inherit them from _config/_shared/team-model.json
    shared_team_model_path = REPO_ROOT / '_config' / '_shared' / 'team-model.json'
    if shared_team_model_path.exists():
        shared_team_model = json.loads(shared_team_model_path.read_text())
        for key in ('teamTypes', 'teamDependencyTypes'):
            org_design.setdefault(key, shared_team_model.get(key, []))
    groups = payload.get('groups', []) if isinstance(payload, dict) else []
    team_pairs = list(iter_team_groups(groups))
    teams = [team for _, team in team_pairs]

    team_ids = [team.get('id') for team in teams if team.get('id')]
    duplicate_team_ids = sorted({team_id for team_id in team_ids if team_ids.count(team_id) > 1})
    for team_id in duplicate_team_ids:
        errors.append(f'{domain_dir.name}: duplicate team id: {team_id}')

    team_id_set = set(team_ids)
    brick_ids = set(bricks)
    valid_types = {str(item.get('id', '')) for item in org_design.get('teamTypes', [])}
    valid_dependency_types = {str(item.get('id', '')) for item in org_design.get('teamDependencyTypes', [])}

    for team in teams:
        team_id = team.get('id', '<missing-id>')

        team_type = team.get('type')
        if valid_types and team_type not in valid_types:
            errors.append(f'{domain_dir.name}: team {team_id} has type {team_type} not in orgDesign.teamTypes')

        headcount = (team.get('teamHeadcount') or {}).get('headcount')
        if headcount is not None and (not isinstance(headcount, int) or headcount < 0):
            errors.append(f'{domain_dir.name}: team {team_id} teamHeadcount.headcount must be a non-negative integer')

        for dependency in team.get('otherTeamDependencies', []) or []:
            dependency_id = dependency.get('teamId')
            if dependency_id and dependency_id not in team_id_set:
                errors.append(f'{domain_dir.name}: team {team_id} references missing team {dependency_id}')
            dependency_type = dependency.get('type')
            if valid_dependency_types and dependency_type and dependency_type not in valid_dependency_types:
                errors.append(f'{domain_dir.name}: team {team_id} uses dependency type {dependency_type} not in orgDesign.teamDependencyTypes')

        for ref in team.get('brickDependencies', []) or []:
            ref_id = str(ref.get('brickId', '')).strip()
            if not ref_id:
                errors.append(f'{domain_dir.name}: team {team_id} has brickDependencies entry without brickId')
                continue
            if brick_ids and ref_id not in brick_ids:
                errors.append(f'{domain_dir.name}: team {team_id} links missing brick {ref_id}')


def _walk_collect(node, list_key, out):
    """Collect entries of every `list_key` array across a nested group tree."""
    if isinstance(node, dict):
        for item in node.get(list_key, []) or []:
            if isinstance(item, dict):
                out.append(item)
        for key in ('rootGroups', 'subGroups', 'groups', 'channels'):
            for child in node.get(key, []) or []:
                _walk_collect(child, list_key, out)
    elif isinstance(node, list):
        for child in node:
            _walk_collect(child, list_key, out)


def _report_duplicates(domain_dir, label, ids, errors):
    seen = set()
    for value in ids:
        if value in seen:
            errors.append(f'{domain_dir.name}: duplicate {label} id: {value}')
        seen.add(value)


def _kpi_node_names(node, out, ids_out=None):
    if not isinstance(node, dict):
        return
    name = str(node.get('name', '')).strip()
    if name:
        out.add(name)
    if ids_out is not None:
        node_id = str(node.get('id', '')).strip()
        if node_id:
            ids_out.add(node_id)
    for key in ('top', 'branches', 'children'):
        child = node.get(key)
        if isinstance(child, dict):
            _kpi_node_names(child, out, ids_out)
        elif isinstance(child, list):
            for item in child:
                _kpi_node_names(item, out, ids_out)


def validate_cross_references(domain_dir, bricks, errors):
    """Cross-file reference checks: deployment→brick, brick→asset,
    stream→brick, jtbd→stream|brick, insight→customer/job/KPI-name."""
    brick_ids = set(bricks)

    # --- streams ---
    stream_ids = set()
    stream_path = domain_dir / 'product-bricks' / 'product-stream.json'
    if stream_path.exists():
        payload = load_json(stream_path, errors)
        if payload is not None:
            streams = []
            _walk_collect(payload, 'streams', streams)
            _report_duplicates(domain_dir, 'stream', [s.get('id') for s in streams if s.get('id')], errors)
            stream_ids = {str(s.get('id', '')).strip() for s in streams if s.get('id')}
            if brick_ids:
                for stream in streams:
                    stream_id = stream.get('id', '<missing-id>')
                    for dependency in stream.get('brickDependencies', []) or []:
                        if not isinstance(dependency, dict):
                            continue
                        target = str(dependency.get('targetBrickId', '')).strip()
                        if target and target not in brick_ids:
                            errors.append(f'{domain_dir.name}: stream {stream_id} references missing brick {target}')

    # --- data assets ---
    asset_ids = set()
    assets_path = domain_dir / 'data' / 'data-assets.json'
    if assets_path.exists():
        payload = load_json(assets_path, errors)
        if payload is not None:
            assets = []
            _walk_collect(payload, 'assets', assets)
            _report_duplicates(domain_dir, 'data asset', [a.get('id') for a in assets if a.get('id')], errors)
            asset_ids = {str(a.get('id', '')).strip() for a in assets if a.get('id')}

    # --- brick dataDependencies -> assets ---
    bricks_path = domain_dir / 'product-bricks' / 'product-bricks.json'
    if asset_ids and bricks_path.exists():
        payload = load_json(bricks_path, errors)
        if payload is not None:
            for brick in iter_product_bricks(payload):
                brick_id = brick.get('id', '<missing-id>')
                for data_dependency in brick.get('dataDependencies', []) or []:
                    if not isinstance(data_dependency, dict):
                        continue
                    asset_id = str(data_dependency.get('assetId', '')).strip()
                    if asset_id and asset_id not in asset_ids:
                        errors.append(f'{domain_dir.name}: brick {brick_id} data dependency references missing asset {asset_id}')

    # --- deployment deployedBricks -> bricks ---
    deployment_path = domain_dir / 'product-deployments' / 'deployment.json'
    if brick_ids and deployment_path.exists():
        payload = load_json(deployment_path, errors)
        if payload is not None:
            deployed = []
            _walk_collect(payload, 'deployedBricks', deployed)
            for entry in deployed:
                target = str(entry.get('brickId', '')).strip()
                if target and target not in brick_ids:
                    errors.append(f'{domain_dir.name}: deployment references missing brick {target}')

    # --- customers: duplicate ids, jtbd streamsNeeded, KPI names for insights ---
    customer_ids = set()
    customer_job_ids = {}
    customer_kpi_names = {}
    customer_kpi_ids = {}
    customers_path = domain_dir / 'customers' / 'customers.json'
    if customers_path.exists():
        payload = load_json(customers_path, errors)
        if payload is not None:
            customers = []
            _walk_collect(payload, 'customers', customers)
            _report_duplicates(domain_dir, 'customer', [c.get('id') for c in customers if c.get('id')], errors)
            stream_or_brick = stream_ids | brick_ids
            for customer in customers:
                customer_id = str(customer.get('id', '')).strip()
                if customer_id:
                    customer_ids.add(customer_id)
                job_ids = set()
                for job in customer.get('jobsToBeDone', []) or []:
                    if not isinstance(job, dict):
                        continue
                    if job.get('id'):
                        job_ids.add(str(job.get('id')).strip())
                    if not stream_or_brick:
                        continue
                    for step in job.get('steps', []) or []:
                        if not isinstance(step, dict):
                            continue
                        for needed_key in ('streamsNeeded', 'bricksNeeded'):
                            for needed in step.get(needed_key, []) or []:
                                needed_id = str((needed or {}).get('id', '')).strip() if isinstance(needed, dict) else str(needed or '').strip()
                                if needed_id and needed_id not in stream_or_brick:
                                    errors.append(f'{domain_dir.name}: customer {customer_id} job {job.get("id", "?")} {needed_key} references missing stream/brick {needed_id}')
                customer_job_ids[customer_id] = job_ids
                kpi_names = set()
                kpi_ids = set()
                pyramids = customer.get('kpiPyramids', {})
                if isinstance(pyramids, dict):
                    for pyramid in pyramids.values():
                        _kpi_node_names(pyramid, kpi_names, kpi_ids)
                customer_kpi_names[customer_id] = kpi_names
                customer_kpi_ids[customer_id] = kpi_ids

    # --- insights linkedCustomers -> customer / job / KPI-name joins ---
    insights_path = domain_dir / 'customers' / 'insights.json'
    if customer_ids and insights_path.exists():
        payload = load_json(insights_path, errors)
        if payload is not None:
            for item in payload.get('items', []) or []:
                if not isinstance(item, dict):
                    continue
                item_id = item.get('id', '<missing-id>')
                for linked in item.get('linkedCustomers', []) or []:
                    if not isinstance(linked, dict):
                        continue
                    linked_id = str(linked.get('customerId', '')).strip()
                    if linked_id and linked_id not in customer_ids:
                        errors.append(f'{domain_dir.name}: insight {item_id} references missing customer {linked_id}')
                        continue
                    for job_id in linked.get('jobIds', []) or []:
                        if job_id and job_id not in customer_job_ids.get(linked_id, set()):
                            errors.append(f'{domain_dir.name}: insight {item_id} references missing job {job_id} for customer {linked_id}')
                    for kpi_id in linked.get('kpiIds', []) or []:
                        if kpi_id and kpi_id not in customer_kpi_ids.get(linked_id, set()):
                            errors.append(f'{domain_dir.name}: insight {item_id} references missing KPI id in {linked_id} pyramids: {kpi_id}')
                    # legacy name-based joins (migrated repo-wide to kpiIds; kept as a guard)
                    for kpi_name in linked.get('kpis', []) or []:
                        if kpi_name and kpi_name not in customer_kpi_names.get(linked_id, set()):
                            errors.append(f'{domain_dir.name}: insight {item_id} references KPI name not in {linked_id} pyramids: {kpi_name}')

    # --- products: duplicate ids + primaryCustomers -> customers ---
    products_path = domain_dir / 'product-deployments' / 'products.json'
    if products_path.exists():
        payload = load_json(products_path, errors)
        if payload is not None:
            portfolio = payload.get('portfolio', {}) if isinstance(payload, dict) else {}
            products = portfolio.get('products', []) or []
            _report_duplicates(domain_dir, 'product', [p.get('id') for p in products if isinstance(p, dict) and p.get('id')], errors)
            if customer_ids:
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    for primary in product.get('primaryCustomers', []) or []:
                        primary_id = str((primary or {}).get('id', '')).strip() if isinstance(primary, dict) else str(primary or '').strip()
                        if primary_id and primary_id not in customer_ids:
                            errors.append(f'{domain_dir.name}: product {product.get("id", "?")} references missing customer {primary_id}')


JOURNEY_STAGES = ['Trigger', 'Discovery', 'Evaluation', 'Trial', 'Engagement', 'Retention']


def validate_journey_stages(domain_dir, warnings):
    path = domain_dir / 'customers' / 'customers.json'
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return  # load/parse failures are reported as errors elsewhere
    for group in payload if isinstance(payload, list) else []:
        for customer in group.get('customers', []) or []:
            for story in customer.get('customerJourneyStories', []) or []:
                stages = [stage.get('stage') for stage in story.get('stages', []) or []]
                bad = [stage for stage in stages if stage not in JOURNEY_STAGES]
                if bad:
                    warnings.append(
                        f"{domain_dir.name}: journey '{story.get('id')}' uses non-standard stage(s) {bad}; "
                        f"journeys model product adoption with stages {JOURNEY_STAGES}")


def validate_relations(domain_dir, errors):
    path = domain_dir / 'customers' / 'relations.json'
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return  # load/parse failures are reported as errors elsewhere
    customer_ids = set()
    customers_path = domain_dir / 'customers' / 'customers.json'
    if customers_path.exists():
        try:
            for group in json.loads(customers_path.read_text()):
                for customer in group.get('customers', []) or []:
                    customer_ids.add(customer.get('id'))
        except (OSError, ValueError):
            return
    stream_ids = set()
    streams_path = domain_dir / 'product-bricks' / 'product-stream.json'
    if streams_path.exists():
        try:
            def walk(node):
                if isinstance(node, dict):
                    for stream in node.get('streams', []) or []:
                        if isinstance(stream, dict):
                            stream_ids.add(stream.get('id'))
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
            walk(json.loads(streams_path.read_text()))
        except (OSError, ValueError):
            pass
    type_ids = {t.get('id') for t in payload.get('relationTypes', []) or []}
    seen = set()
    for relation in payload.get('relations', []) or []:
        rid = relation.get('id')
        if rid in seen:
            errors.append(f'{domain_dir.name}: relations.json duplicate relation id: {rid}')
        seen.add(rid)
        for endpoint in ('from', 'to'):
            value = relation.get(endpoint)
            if customer_ids and value not in customer_ids:
                errors.append(f"{domain_dir.name}: relations.json {rid}: '{endpoint}' is not a customer id: {value}")
        if relation.get('from') == relation.get('to'):
            errors.append(f'{domain_dir.name}: relations.json {rid}: self-loop relation')
        if relation.get('type') not in type_ids:
            errors.append(f"{domain_dir.name}: relations.json {rid}: undeclared relation type: {relation.get('type')}")
        for stream_id in relation.get('streamIds', []) or []:
            if stream_ids and stream_id not in stream_ids:
                errors.append(f'{domain_dir.name}: relations.json {rid}: unknown stream id: {stream_id}')


def validate_domain(domain_dir, strict_ids=False):
    errors = []
    warnings = []
    json_payloads = []

    for json_path in sorted(domain_dir.rglob('*.json')):
        payload = load_json(json_path, errors)
        if payload is not None:
            json_payloads.append((json_path, payload))
            validate_against_schema(domain_dir, json_path, payload, errors)
            if strict_ids and 'evidence' not in json_path.name:
                validate_lowercase_ids(domain_dir, payload, errors,
                    composite_targets=json_path.relative_to(domain_dir).as_posix() == 'residuality/residuality.json')

    bricks = {}
    product_bricks_path = domain_dir / 'product-bricks' / 'product-bricks.json'
    if product_bricks_path.exists():
        payload = load_json(product_bricks_path, errors)
        if payload is not None:
            bricks = collect_bricks(payload)
            validate_product_bricks_model(domain_dir, payload, errors)
            duplicate_bricks = sorted(brick_id for brick_id, values in bricks.items() if len(values) > 1)
            for brick_id in duplicate_bricks:
                errors.append(f'{domain_dir.name}: duplicate product brick id: {brick_id}')

    validate_team_model(domain_dir, bricks, errors)
    validate_cross_references(domain_dir, bricks, errors)
    validate_relations(domain_dir, errors)
    validate_journey_stages(domain_dir, warnings)
    return errors, warnings, len(json_payloads), len(bricks)


def main():
    parser = argparse.ArgumentParser(description='Validate product-domain JSON and core cross-file references.')
    parser.add_argument('--all', action='store_true', help='Validate every product domain. By default, pass one or more domain IDs for scoped validation.')
    parser.add_argument('--strict-ids', action='store_true', help='Also check lowercase/simple ID conventions. This can flag intentional evidence or trace identifiers.')
    parser.add_argument('domains', nargs='*', help='Domain IDs to validate.')
    args = parser.parse_args()

    try:
        if args.domains:
            domain_dirs = [resolve_domain_dir(domain) for domain in args.domains]
        elif args.all:
            domain_dirs = discover_domain_dirs()
        else:
            parser.error('pass one or more domain IDs, or use --all for a full repository scan')
    except (OSError, ValueError) as error:
        parser.error(str(error))

    all_errors = []
    all_warnings = []
    summaries = []
    for domain_dir in domain_dirs:
        if not domain_dir.exists():
            all_errors.append(f'{domain_dir.name}: domain directory does not exist')
            continue
        errors, warnings, json_count, brick_count = validate_domain(domain_dir, strict_ids=args.strict_ids)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        summaries.append((domain_dir.name, json_count, brick_count))

    if all_warnings:
        print(f'Warnings ({len(all_warnings)}):')
        for warning in all_warnings:
            print(f'- {warning}')

    if all_errors:
        print('Domain validation failed:')
        for error in all_errors:
            print(f'- {error}')
        return 1

    print(f'Domain validation passed: {len(summaries)} domains checked.')
    for domain, json_count, brick_count in summaries:
        print(f'- {domain}: {json_count} JSON files, {brick_count} product bricks')
    return 0


if __name__ == '__main__':
    sys.exit(main())

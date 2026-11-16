"""Render a domain's commercial model without dependencies or provider APIs."""
from html import escape
import json
from pathlib import Path
import re

from domain_cli import load_domain_args
from generator_common import domain_docs_path, domain_source_path, template_path
import project_paths
from value_growth_model import market_totals, reference_catalog, validate_value_growth, walk


def p(text, cls=''):
    return f'<p class="{cls}">{escape(str(text))}</p>' if text else ''


def items(values, ordered=False):
    tag = 'ol' if ordered else 'ul'
    return f'<{tag}>' + ''.join(f'<li>{escape(v)}</li>' for v in values) + f'</{tag}>'


def pairs(values):
    return '<dl>' + ''.join(f'<dt>{escape(label)}</dt><dd>{escape(text)}</dd>' for label, text in values) + '</dl>'


def money(value, currency):
    return f'{currency} {value:,.0f}' if value >= 1000 else f'{currency} {value:,.2f}'


class Renderer:
    def __init__(self, model, catalog):
        self.model = model
        self.catalog = catalog
        self.sources = {s['id']: (index, s) for index, s in enumerate(model.get('sources', []), 1)}
        self.entry_models = {m['id']: m for m in model.get('entryStrategy', {}).get('models', [])}

    def evidence(self, item):
        ev = item['evidence']
        labels = {'observed': 'Sourced fact', 'inferred': 'Assessment', 'illustrative': 'Illustrative assumption'}
        links = ' '.join(f'<a href="#source-{escape(ref)}" title="{escape(self.sources[ref][1]["title"], quote=True)}">[{self.sources[ref][0]}]</a>' for ref in ev['sourceIds'])
        return (f'<div class="evidence"><span class="badge {ev["kind"]}">{labels[ev["kind"]]}</span> '
                f'{escape(ev["note"])} {links}</div>')

    def related(self, segment):
        links = []
        for ref in segment['customerRefs']:
            person = self.catalog['customers'][ref['customerId']]
            base = '../customers/landing_pages/' + person['id'] + '.html'
            links.append(f'<a href="{escape(base)}">{escape(person["name"])}</a>')
            jobs = {job['id']: job for job in person.get('jobsToBeDone', [])}
            for job_id in ref['jobIds']:
                links.append(f'<a href="{escape(base)}#JobsTab">{escape(jobs[job_id]["name"])}</a>')
            kpis = {node['id']: node for _, node in walk(person.get('kpiPyramids', {})) if 'id' in node}
            for kpi_id in ref['kpiIds']:
                links.append(f'<a href="{escape(base)}#KPITab">KPI: {escape(kpis[kpi_id]["name"])}</a>')
        for group, field, directory in [('products', 'productIds', 'product-deployments'), ('competitors', 'competitorIds', 'competition')]:
            for ref in segment[field]:
                name = self.catalog[group][ref]['name']
                links.append(f'<a href="../{directory}/landing_pages/{escape(ref)}.html">{escape(name)}</a>')
        return '<div class="related" aria-label="Related domain models">' + ''.join(links) + '</div>'

    def value(self):
        rows = []
        for s in self.model.get('segments', []):
            rows.append('<tr><th scope="row"><a href="#segment-' + s['id'] + '">' + escape(s['name']) + '</a></th>'
                        + ''.join('<td>' + escape(s[k]) + '</td>' for k in ('outcome', 'valueUnit', 'pricingUnit')) + '</tr>')
        content = p('Read each offer from the customer outcome through the unit charged. A usage measure is useful only when it tracks meaningful progress.')
        content += '<div class="table-scroll"><table><caption>Value and pricing by offering</caption><thead><tr><th>Offering</th><th>Customer outcome</th><th>Value unit</th><th>Pricing unit</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
        for s in self.model.get('segments', []):
            content += (f'<article class="panel segment" id="segment-{s["id"]}"><h3>{escape(s["name"])}</h3>' + p(s['summary'])
                        + pairs([('Charging model', s['pricingModel']), ('How to prove value', s['valueProof'])])
                        + self.related(s) + self.evidence(s) + '</article>')
        if self.model.get('benchmarks'):
            content += '<h3>Public pricing examples</h3>' + p('Examples have different geographies, fee bases and bundled responsibilities. They are reference points for the pricing unit, not a like-for-like price ranking.')
            content += '<div class="grid">'
            for b in self.model['benchmarks']:
                content += (f'<article class="panel"><h4><a href="../competition/landing_pages/{b["competitorId"]}.html">{escape(b["name"])}</a></h4>'
                            + p(b['price'], 'price') + p(b['metric'])
                            + p(f'{b["geography"]} · {b["currency"]} · Checked {b["observedOn"]}', 'muted')
                            + pairs([('Includes / applies to', b['scope']), ('Comparison limit', b['caveat'])]) + self.evidence(b) + '</article>')
            content += '</div>'
        return content

    def selling(self):
        f = self.model['framework']
        content = p(f['summary']) + '<div class="grid strategy-grid">'
        for strategy in f['strategies']:
            content += '<article class="panel"><h3>' + escape(strategy['name']) + '</h3>' + p(strategy['definition']) + '</article>'
        content += '</div>' + self.evidence(f)
        content += p('Selling motion describes how a purchase spreads and is approved. Growth positioning describes the offering relative to an alternative. An offer can combine a bottom-up entry with an enterprise sales process.')
        for s in self.model.get('segments', []):
            selling, position = s['selling'], s['positioning']
            content += f'<article class="panel"><div class="card-heading"><h3>{escape(s["name"])}</h3><span class="badge">{escape(selling["motion"].replace("-", " ").title())}</span></div>'
            content += '<div class="grid"><div>' + pairs([(label, selling[key]) for label, key in [('Users', 'users'), ('Champions', 'champions'), ('Decision-makers', 'buyers'), ('Who pays', 'payers')]]) + '</div><div>'
            content += p(selling['rationale']) + '<h4>Routes to market</h4>' + items(selling['channels']) + '</div></div>'
            content += '<div class="positioning">' + pairs([('Growth position', position['strategy'].title()), ('Compared with', position['alternative']), ('Reasoning', position['rationale'])])
            content += '<h4>What must hold</h4>' + items(position['conditions']) + '</div>' + self.evidence(s) + '</article>'
        if self.model.get('providers'):
            content += '<h3>Provider perspectives</h3>'
            for provider in self.model['providers']:
                content += (f'<article class="panel provider" id="provider-{provider["id"]}"><h3><a href="../competition/landing_pages/{provider["competitorId"]}.html">{escape(provider["name"])}</a></h3>'
                            + p(provider['summary']) + pairs([(v['label'], v['text']) for v in provider['points']]) + self.evidence(provider) + '</article>')
        return content

    def entry_strategy(self):
        strategy = self.model.get('entryStrategy')
        if not strategy:
            return ''
        content = '<h3 id="entry-options">Freemium, trials &amp; paid entry</h3>' + p(strategy['summary'])
        content += '<div class="grid entry-models">'
        for model in strategy['models']:
            content += (f'<article class="panel entry-model" id="entry-model-{model["id"]}"><h4>{escape(model["name"])}</h4>'
                        + p(model['definition'])
                        + pairs([('Where it fits', model['bestFit']), ('Path to paid value', model['conversion']), ('Limits', model['limits'])])
                        + '</article>')
        content += '</div>' + self.evidence(strategy)
        if strategy['examples']:
            content += '<h3>Current provider examples</h3><div class="grid">'
            for example in strategy['examples']:
                content += (f'<article class="panel entry-example" id="entry-example-{example["id"]}"><h4>'
                            f'<a href="../competition/landing_pages/{example["competitorId"]}.html">{escape(example["name"])}</a></h4>'
                            + p(example['summary']) + p(example['caveat'], 'muted') + self.evidence(example) + '</article>')
            content += '</div>'
        return '<div class="entry-strategy">' + content + '</div>'

    def entry_offer(self, segment):
        offer = segment['activation'].get('entryOffer')
        if not offer:
            return ''
        links = ''.join(f'<a href="#entry-model-{ref}">{escape(self.entry_models[ref]["name"])}</a>' for ref in offer['modelIds'])
        return (f'<div class="positioning entry-offer" id="entry-offer-{segment["id"]}"><h4>Entry model &amp; conversion</h4>'
                + p(offer['rationale']) + '<div class="related" aria-label="Suggested entry models">' + links + '</div>'
                + pairs([(label, offer[key]) for label, key in [
                    ('Freemium fit', 'freemiumFit'), ('Free-trial fit', 'trialFit'),
                    ('Evaluation scope', 'evaluationScope'), ('Limits and costs', 'limits'),
                    ('Paid conversion trigger', 'paidTrigger'), ('Suggested conversion measure', 'conversionMetric')]])
                + self.evidence(offer) + '</div>')

    def activation(self):
        content = p('Track the first real customer outcome separately from a signup, download or successful sandbox request.')
        content += self.entry_strategy()
        if self.model.get('segments'):
            content += '<h3>Activation and entry fit by offering</h3>'
        content += '<div class="grid">'
        for s in self.model.get('segments', []):
            a = s['activation']
            content += f'<article class="panel" id="activation-{s["id"]}"><h3>' + escape(s['name']) + '</h3>' + pairs([(label, a[key]) for label, key in [('Entry experience', 'entry'), ('First value', 'firstValue'), ('Repeated value', 'repeatValue'), ('Expansion', 'expansion')]])
            content += '<h4>Friction to resolve</h4>' + items(a['frictions']) + self.evidence(s) + self.entry_offer(s) + '</article>'
        content += '</div>'
        if self.model.get('growthLoops'):
            content += '<h3>Growth mechanisms to test</h3>'
            for loop in self.model['growthLoops']:
                content += '<article class="panel"><h4>' + escape(loop['name']) + '</h4>' + items(loop['steps'], True)
                content += '<h5>Measure</h5>' + items(loop['signals']) + p(loop['constraint'], 'callout') + self.evidence(loop) + '</article>'
        return content

    def market(self):
        market = self.model['market']
        content = p(market['summary']) + p(market['boundary'], 'callout') + '<div class="grid">'
        for context in market['context']:
            content += '<article class="panel"><h3>' + escape(context['label']) + '</h3>' + p(context['value'], 'price') + p(context['description']) + self.evidence(context) + '</article>'
        content += '</div>'
        scenarios = market['scenarios']
        if scenarios:
            s = scenarios[0]
            content += '<article class="panel calculator"><h3>Explore annual revenue opportunity</h3>' + p('TAM is the total revenue opportunity within the stated boundary. SAM applies the serviceable share. SOM applies an obtainable share of SAM at the stated horizon; it is an annual run rate, not cumulative revenue.')
            content += '<form id="market-form"><label>Scenario<select id="scenario">' + ''.join(f'<option value="{i}">{escape(v["name"])}</option>' for i, v in enumerate(scenarios)) + '</select></label>'
            content += '<div class="grid inputs">'
            for field, label, value, maximum, step in [
                ('units', s['unitLabel'], s['units'], '1e20', 'any'),
                ('revenuePerUnit', s['revenueLabel'], s['revenuePerUnit'], '1e20', 'any'),
                ('serviceableShare', 'Serviceable share of TAM (%)', s['serviceableShare'] * 100, '100', 'any'),
                ('obtainableShare', 'Obtainable share of SAM (%)', s['obtainableShare'] * 100, '100', 'any')]:
                content += f'<label><span id="label-{field}">{escape(label)}</span><input id="{field}" type="number" min="0" max="{maximum}" step="{step}" required value="{value}"></label>'
            content += '</div><button type="button" id="reset-market">Reset scenario</button></form>'
            content += '<p id="scenario-scope" class="muted"></p><p id="market-state" class="callout">Scenario assumptions; not a market forecast.</p><p id="market-error" role="alert" hidden></p>'
            totals = market_totals(s)
            content += '<div class="market-results" aria-live="polite" aria-atomic="true">'
            for key, definition in [('tam', 'Units × annual revenue per unit'), ('sam', 'TAM × serviceable share'), ('som', 'SAM × obtainable share')]:
                content += f'<div><h4>{key.upper()}</h4><output id="result-{key}">{money(totals[key], s["currency"])}</output>{p(definition)}</div>'
            content += '</div><noscript><p>The figures above use the first scenario. Enable JavaScript to adjust assumptions; all original scenarios are recorded below.</p></noscript></article>'
            content += '<h3>Scenario assumptions and limits</h3>'
            for s in scenarios:
                totals = market_totals(s)
                content += f'<details class="panel" id="scenario-{s["id"]}"><summary>{escape(s["name"])}</summary>'
                content += p(f'{s["geography"]} · Base {s["baseYear"]} · {s["horizonYears"]}-year horizon · Annual {s["currency"]} provider revenue')
                content += pairs([(s['unitLabel'], f'{s["units"]:,.0f}'), (s['revenueLabel'], str(s['revenuePerUnit'])), ('Serviceable share', f'{s["serviceableShare"]:.1%}'), ('Obtainable share of SAM', f'{s["obtainableShare"]:.1%}')])
                content += p(' · '.join(key.upper() + ' ' + money(value, s['currency']) for key, value in totals.items()))
                content += '<h4>Assumptions</h4>' + items(s['assumptions']) + '<h4>Limits</h4>' + items(s['limitations']) + self.evidence(s) + '</details>'
        content += '<h3>Market boundaries and exclusions</h3>' + items(market['exclusions'])
        return content

    def economics(self):
        content = '<div class="grid">'
        for metric in self.model.get('economics', []):
            content += '<article class="panel"><h3>' + escape(metric['name']) + '</h3>' + p(metric['formula'], 'formula')
            content += p(metric['whyItMatters']) + p(metric['measurementCautions'], 'muted') + p('Data: ' + metric['availability'].replace('-', ' '), 'availability') + self.evidence(metric) + '</article>'
        content += '</div>'
        if self.model.get('constraints'):
            content += '<h3>Constraints that change the growth model</h3>'
            for c in self.model['constraints']:
                content += '<article class="panel"><h4>' + escape(c['title']) + '</h4>' + p(c['description']) + self.evidence(c) + '</article>'
        return content

    def source_list(self):
        content = p('Sourced fact = directly supported observation. Assessment = analysis of the cited evidence. Illustrative assumption = an input to explore, not a measured market fact.') + '<ol class="sources">'
        for source in self.model.get('sources', []):
            content += (f'<li id="source-{source["id"]}"><a href="{escape(source["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(source["title"])}</a>'
                        + p(source['publisher'] + ' · Checked ' + source['accessed'] + (' · Published ' + source['published'] if source.get('published') else ''), 'muted') + '</li>')
        return content + '</ol>'


def create_docs(domain):
    root = Path(domain_source_path(domain['id']))
    source = root / 'business/value-growth.json'
    model = json.loads(source.read_text(encoding='utf-8')) if source.is_file() else {
        'schemaVersion': '1.0', 'domainId': domain['id'], 'status': 'draft', 'title': 'Value & Growth'}
    errors = validate_value_growth(model, domain['id'], root)
    if errors:
        raise ValueError(str(source) + ':\n' + '\n'.join(errors))
    templates = Path(template_path('value-growth'))
    renderer = Renderer(model, reference_catalog(root))
    sections = []
    if model.get('segments'):
        intro = p(model.get('scope', ''), 'muted') + (templates / 'value-chain.html').read_text(encoding='utf-8')
        sections.append(('value', 'Value & monetization', intro + renderer.value()))
    if model.get('segments') and model.get('framework'):
        sections.append(('selling', 'Selling & positioning', renderer.selling()))
    if model.get('segments') or model.get('entryStrategy') or model.get('growthLoops'):
        sections.append(('activation', 'Activation & growth', renderer.activation()))
    if model.get('market'):
        sections.append(('market', 'Market opportunity', renderer.market()))
    if model.get('economics'):
        sections.append(('economics', 'Business economics', renderer.economics()))
    if model.get('sources'):
        sections.append(('sources', 'Sources & evidence', renderer.source_list()))
    content = ''.join(
        f'<section class="tabcontent" id="tab_content_{anchor}" data-tab="{anchor}" aria-labelledby="tab_{anchor}">'
        f'<div id="{anchor}"><h2 class="section-heading" id="heading-{anchor}">{escape(title)}</h2>{body}</div></section>'
        for anchor, title, body in sections)
    tabs = ('<div class="tab" aria-label="Value and growth sections">' + ''.join(
        f'<button type="button" class="tablinks" id="tab_{anchor}" onclick="openTab(\'{anchor}\')">{escape(title)}</button>'
        for anchor, title, _ in sections) + '</div>') if sections else ''
    if not sections:
        content = '<div class="panel"><h2>Value & Growth is not yet documented</h2><p>This domain has no commercial model to display yet.</p></div>'
    elif model['status'] == 'draft':
        content = '<p class="callout">Draft commercial model — some sections are still being developed.</p>' + content
    folder = project_paths.DOCS_ROOT / domain_docs_path(domain['id'], 'value-growth')
    home = (f'<a href="../start/index.html">{escape(domain["name"])} Home</a>'
            if (folder.parent / 'start/index.html').is_file() else escape(domain['name']))
    breadcrumbs = ('<div class="breadcrumbs-container"><span class="breadcrumb">' + home +
                   '</span><span aria-hidden="true">&nbsp;&nbsp;&gt;&nbsp;&nbsp;</span>' +
                   '<span class="breadcrumb">' + escape(model['title']) + '</span></div>')
    replacements = {
        'title': escape(model['title']), 'domain_name': escape(domain['name']),
        'summary': p(model.get('summary', '')),
        'metadata': p('Updated ' + model['updated'], 'metadata') if model.get('updated') else '',
        'tabs': tabs, 'content': content, 'breadcrumbs': breadcrumbs,
        'breadcrumbs_style': (templates.parent / '_imports/breadcrumbs/style.html').read_text(encoding='utf-8'),
        'tabs_style': (templates.parent / '_imports/tabs/style.html').read_text(encoding='utf-8'),
        'tabs_script': (templates.parent / '_imports/tabs/script.html').read_text(encoding='utf-8'),
        'tokens_style': (templates.parent / '_imports/tokens/style.html').read_text(encoding='utf-8'),
        'app_style': (templates / 'style.css').read_text(encoding='utf-8'),
        'app_script': (templates / 'script.js').read_text(encoding='utf-8'),
        'market_data': json.dumps(model.get('market', {}).get('scenarios', []), ensure_ascii=True).replace('<', '\\u003c').replace('&', '\\u0026'),
    }
    page = re.sub(r'\$\{([a-z_]+)\}', lambda m: replacements.get(m[1], m[0]), (templates / 'index.html').read_text(encoding='utf-8'))
    icon = (templates / 'icons/logo.svg').read_bytes()
    if not folder.resolve().is_relative_to(project_paths.DOCS_ROOT):
        raise ValueError('Value & Growth output resolves outside the docs folder')
    # Prepare everything before replacing the previous page.
    (folder / 'icons').mkdir(parents=True, exist_ok=True)
    (folder / 'icons/logo.svg').write_bytes(icon)
    (folder / 'index.html').write_text(page, encoding='utf-8')
    print(f'{domain["name"]}: Value & Growth {model["status"]}, {len(model.get("segments", []))} offerings')


if __name__ == '__main__':
    domain, _ = load_domain_args()
    try:
        create_docs(domain)
    except (OSError, ValueError) as error:
        raise SystemExit(f'Error: {error}')

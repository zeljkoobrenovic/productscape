"""Render the optional beginner tutorial as a self-contained reading page."""
import html
import json
import math
from pathlib import Path
import re

from domain_cli import load_domain_args
from generator_common import domain_docs_path, domain_source_path, template_path
import project_paths
from tutorial_model import tutorial_image_path, tutorial_images, validate_tutorial


def escape(value):
    return html.escape(str(value), quote=True)


def paragraphs(value):
    return ''.join(f'<p>{escape(part.strip())}</p>' for part in value.split('\n\n') if part.strip())


def labeled(label, value):
    return f'<div class="labeled"><p class="label">{escape(label)}</p>{paragraphs(value)}</div>'


def bullet_list(items):
    return '<ul>' + ''.join(f'<li>{paragraphs(item)}</li>' for item in items) + '</ul>'


def illustration(media, extra_class=''):
    label = media.get('title') or media['alt']
    caption = paragraphs(media['caption']) if media.get('caption') else ''
    return (f'<figure class="tutorial-illustration {extra_class}">'
            f'<a class="illustration-link" href="{escape(media["src"])}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{escape(label)} — open full image in a new tab">'
            f'<img src="{escape(media["src"])}" alt="{escape(media["alt"])}" loading="lazy" decoding="async">'
            '</a><figcaption>' + caption + '<span class="image-hint">Click the image to open it in a new tab.</span>'
            '</figcaption></figure>')


def entries(items, title_key, fields):
    result = []
    for item in items:
        content = f'<h3>{escape(item[title_key])}</h3>'
        for key, label in fields:
            if item.get(key):
                content += labeled(label, item[key]) if label else paragraphs(item[key])
            if key == 'meaning':
                content += ''.join(illustration(media, 'concept-illustration') for media in item.get('media', []))
        result.append(f'<div class="entry">{content}</div>')
    return ''.join(result)


def render_sections(model):
    sections = []

    def add(anchor, title, content):
        if content:
            sections.append((anchor, title, content))

    if model.get('learningGoals'):
        add('learning-goals', 'What you will learn', bullet_list(model['learningGoals']))
    intro = model.get('introduction')
    if intro:
        add('introduction', 'Start with the everyday need',
            paragraphs(intro['whatItIs']) + paragraphs(intro['whyItMatters']) +
            '<aside class="example">' + labeled('A familiar comparison', intro['familiarComparison']) +
            labeled('Where the comparison stops', intro['whereComparisonBreaks']) + '</aside>')
    participant_map = ''.join(illustration(media) for media in model.get('participantsOverview', {}).get('media', []))
    add('participants', 'The people involved', participant_map + entries(model.get('participants', []), 'name', [
        ('role', ''), ('caresAbout', 'What matters to them')]))
    add('concepts', 'The key concepts', entries(model.get('concepts', []), 'term', [
        ('meaning', ''), ('example', 'For example'), ('whyItMatters', 'Why it matters')]))
    if model.get('history'):
        timeline = []
        for item in model['history']:
            source = (f'<p class="source"><a href="{escape(item["sourceUrl"])}" rel="noreferrer">'
                      f'Source for {escape(item["period"])}</a></p>') if item.get('sourceUrl') else ''
            timeline.append(f'<li><h3>{escape(item["period"])}</h3>' + paragraphs(item['change']) +
                            labeled('What this helps explain', item['whyItMatters']) + source + '</li>')
        add('history', 'A little history', paragraphs(model.get('historyNote', '')) +
            '<ol class="timeline">' + ''.join(timeline) + '</ol>')
    case = model.get('walkthrough')
    if case:
        steps = []
        for step in case['steps']:
            content = f'<h4>{escape(step["title"])}</h4>' + paragraphs(step['whatHappens'])
            content += labeled('Why this step matters', step['whyItMatters'])
            if step.get('watchOut'):
                content += '<aside class="example">' + labeled('When things go differently', step['watchOut']) + '</aside>'
            steps.append(f'<li>{content}</li>')
        add('walkthrough', 'Follow one complete example', f'<h3>{escape(case["title"])}</h3>' +
            paragraphs(case['setup']) + ''.join(illustration(media) for media in case.get('media', [])) +
            '<ol class="steps">' + ''.join(steps) + '</ol>' +
            labeled('The outcome', case['outcome']))
    add('value', 'Value, money, and incentives', entries(model.get('valueAndIncentives', []), 'title', [
        ('explanation', ''), ('example', 'For example')]))
    add('challenges', 'What makes this domain difficult', entries(model.get('challenges', []), 'title', [
        ('whyHard', ''), ('tradeOff', 'The competing needs'), ('example', 'In practice'),
        ('commonApproach', 'How people respond, and its limits')]))
    add('misconceptions', 'Common misunderstandings', entries(model.get('misconceptions', []), 'belief', [
        ('reality', 'A better way to understand it')]))
    if model.get('takeaways'):
        add('takeaways', 'The ideas to take with you', bullet_list(model['takeaways']))
    if model.get('knowledgeChecks'):
        questions = []
        for number, check in enumerate(model['knowledgeChecks'], 1):
            questions.append(f'<div class="entry"><h3>{number}. {escape(check["question"])}</h3>' +
                             '<details><summary>Reveal answer'
                             f'<span class="visually-hidden"> to question {number}</span></summary>' +
                             '<div class="answer">' + paragraphs(check['answer']) +
                             labeled('The reasoning', check['explanation']) + '</div></details></div>')
        add('knowledge-checks', 'Try it for yourself',
            '<p>Pause and think through each situation, then open the answer.</p>' + ''.join(questions))
    if model.get('nextQuestions'):
        add('next-questions', 'Questions to ask a practitioner', bullet_list(model['nextQuestions']))
    if model.get('furtherReading'):
        add('further-reading', 'Keep learning', '<ul class="reading-list">' + ''.join(
            f'<li><a href="{escape(item["url"])}" rel="noreferrer">{escape(item["title"])}</a>' +
            paragraphs(item['whyRead']) + '</li>' for item in model['furtherReading']) + '</ul>')
    return sections


def reading_minutes(sections):
    prose = html.unescape(re.sub(r'<[^>]*>', ' ', ' '.join(content for _, _, content in sections)))
    return max(1, math.ceil(len(prose.split()) / 200))


def create_docs(domain):
    source = Path(domain_source_path(domain['id'], 'tutorial/tutorial.json'))
    model = json.loads(source.read_text(encoding='utf-8')) if source.is_file() else {
        'schemaVersion': '1.0', 'domainId': domain['id'], 'status': 'draft',
        'title': domain['name'] + ': an introduction',
    }
    errors = validate_tutorial(model, domain['id'], source.parent)
    if errors:
        raise ValueError(str(source) + ':\n' + '\n'.join(errors))

    # Read and render every input before touching a previous page.
    templates = Path(template_path('tutorial'))
    template = (templates / 'index.html').read_text(encoding='utf-8')
    style = (templates / 'style.css').read_text(encoding='utf-8')
    tokens = (templates.parent / '_imports/tokens/style.html').read_text(encoding='utf-8')
    sections = render_sections(model)
    has_content = any(anchor != 'learning-goals' for anchor, _, _ in sections)
    status = ''
    if not has_content:
        status = '<div class="notice"><h2>This introduction is not written yet</h2><p>There is no tutorial to read here yet. Please check back later.</p></div>'
    elif model['status'] == 'draft':
        status = '<div class="notice"><strong>Draft introduction</strong><p>This tutorial is still being written and may have gaps.</p></div>'
    toc = ('<nav class="contents" aria-label="Tutorial contents"><h2>In this guide</h2><ol>' + ''.join(
        f'<li><a href="#{anchor}">{escape(title)}</a></li>' for anchor, title, _ in sections
    ) + '</ol></nav>') if sections else ''
    body = ''.join(f'<section id="{anchor}" aria-labelledby="heading-{anchor}">'
                   f'<p class="chapter-number">{number:02d}</p>'
                   f'<h2 id="heading-{anchor}">{escape(title)}</h2>{content}</section>'
                   for number, (anchor, title, content) in enumerate(sections, 1))
    folder = project_paths.DOCS_ROOT / domain_docs_path(domain['id'], 'tutorial')
    home = folder.parent / 'start/index.html'
    domain_link = (f'<a href="../start/index.html">{escape(domain["name"])}</a>' if home.is_file()
                   else f'<span>{escape(domain["name"])}</span>')
    metadata = (f'<span>About {reading_minutes(sections)} min to read</span>' if has_content else '')
    if model.get('updated'):
        metadata += f'<span>Updated <time datetime="{escape(model["updated"])}">{escape(model["updated"])}</time></span>'
    replacements = {
        'title': escape(model['title']), 'domain_link': domain_link,
        'audience': labeled('Who this is for', model['audience']) if model.get('audience') else '',
        'scope': labeled('What this guide covers', model['scope']) if model.get('scope') else '',
        'metadata': metadata, 'status': status, 'contents': toc, 'sections': body,
        'tokens_style': tokens, 'app_style': style,
    }
    # Single-pass substitution keeps authored text such as ${title} literal.
    rendered = re.sub(r'\$\{([a-z_]+)\}', lambda match: replacements.get(match[1], match[0]), template)
    if not folder.resolve().is_relative_to(project_paths.DOCS_ROOT):
        raise ValueError(f'Tutorial output resolves outside the docs folder: {folder}')
    assets = {}
    for _, media in tutorial_images(model):
        destination = tutorial_image_path(folder, media['src'])
        assets[destination] = tutorial_image_path(source.parent, media['src']).read_bytes()
    folder.mkdir(parents=True, exist_ok=True)
    for destination, data in assets.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (folder / 'index.html').write_text(rendered, encoding='utf-8')
    print(f'{domain["name"]}: tutorial {model["status"]}, {len(sections)} sections')


def main():
    domain, _ = load_domain_args()
    try:
        create_docs(domain)
    except (OSError, ValueError) as error:
        raise SystemExit(f'Error: {error}')


if __name__ == '__main__':
    main()

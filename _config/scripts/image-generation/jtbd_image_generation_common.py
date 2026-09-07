#!/usr/bin/env python3
"""Shared JTBD image-generation helpers for provider-specific scripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
sys.path.insert(0, str(REPO_ROOT / "_wiring"))
from project_paths import DOMAINS_ROOT as PRODUCT_DOMAINS_DIR, PROJECT_ROOT

from domain_paths import list_domain_files
PROMPT_INSPIRATION_PATH = SCRIPT_PATH.parent / "jtbd-cartoon-prompt.txt"
DEFAULT_OUTPUT_FORMAT = "png"


@dataclass
class GenerationTarget:
    domain_id: str
    customers_json_path: Path
    customer_name: str
    customer_description: str
    customer_id: str
    job: dict[str, Any]
    step: dict[str, Any] | None
    image_path: Path
    media_src: str
    title: str
    alt: str
    prompt: str
    level: str
    step_index: int | None = None


@dataclass
class GeneratedImage:
    image_bytes: bytes
    output_format: str | None = None


def build_argument_parser(
    *,
    description: str,
    default_model: str,
    default_quality: str = "high",
    output_formats: tuple[str, ...] = ("png", "jpeg", "webp"),
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate.")
    parser.add_argument("--model", default=default_model, help="Image-generation model.")
    parser.add_argument("--quality", default=default_quality, help="Image quality, if supported.")
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=output_formats,
        help="Image output format or preferred file extension.",
    )
    parser.add_argument("--background", default="opaque", help="Image background mode, if supported.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip generation if the target file already exists.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate image files even when they already exist.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Update JSON media references only, without calling the API.",
    )
    parser.add_argument(
        "--lightweight",
        action="store_true",
        help="Generate only one overview image per job, without per-step images.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between API calls.",
    )
    return parser


def load_prompt_inspiration() -> str:
    if not PROMPT_INSPIRATION_PATH.exists():
        return ""
    return PROMPT_INSPIRATION_PATH.read_text(encoding="utf-8").strip()


def list_customer_files(domain_filter: str | None) -> list[Path]:
    return list_domain_files("customers/customers.json", domain_filter, PRODUCT_DOMAINS_DIR)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN json update: {path}")
        return
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def make_job_filename(customer_id: str, job_id: str, output_format: str) -> str:
    return f"jbtd-{slugify(customer_id, 'cust')}-{slugify(job_id, 'job')}.{output_format}"


def make_step_filename(customer_id: str, job_id: str, step_index: int, output_format: str) -> str:
    return (
        f"jbtd-{slugify(customer_id, 'cust')}-{slugify(job_id, 'job')}-{step_index}.{output_format}"
    )


def pick_media_entry(media: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not isinstance(media, list):
        return None
    for item in media:
        if isinstance(item, dict) and item.get("type") == "image":
            return item
    return None


def ensure_media_list(item: dict[str, Any]) -> list[dict[str, Any]]:
    media = item.get("media")
    if not isinstance(media, list):
        media = []
        item["media"] = media
    return media


def upsert_image_media(item: dict[str, Any], media_src: str, title: str, alt: str) -> bool:
    media = ensure_media_list(item)
    entry = pick_media_entry(media)
    changed = False
    if entry is None:
        entry = {"type": "image"}
        media.insert(0, entry)
        changed = True
    for key, value in (("src", media_src), ("title", title), ("alt", alt)):
        if entry.get(key) != value:
            entry[key] = value
            changed = True
    return changed


def build_capability_summary(step: dict[str, Any] | None) -> str:
    if not step:
        return ""
    capabilities = step.get("capabilitiesNeeded") or []
    lines: list[str] = []
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        name = capability.get("name") or capability.get("id") or "Capability"
        support = capability.get("how_it_supports") or ""
        if support:
            lines.append(f"- {name}: {support}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def build_storyline(job: dict[str, Any]) -> str:
    steps = job.get("steps") or []
    labels: list[str] = []
    for index, step in enumerate(steps, start=1):
        step_name = step.get("step") or f"Step {index}"
        labels.append(f"{index}. {step_name}")
    return " | ".join(labels)


def build_job_prompt(
    domain_id: str,
    customer_name: str,
    customer_description: str,
    job: dict[str, Any],
    inspiration: str,
) -> str:
    steps = job.get("steps") or []
    step_lines = []
    for index, step in enumerate(steps, start=1):
        step_title = step.get("step") or f"Step {index}"
        step_desc = step.get("description") or ""
        step_lines.append(f"{index}. {step_title}: {step_desc}")

    outcome = job.get("outcome") or ""
    what_it_is = job.get("what_it_is") or ""

    return f"""
Create a single polished landscape explainer board for this job to be done.

Domain: {domain_id}
Customer: {customer_name}
Customer context: {customer_description}
Job to be done: {job.get("name", "")}
What it is: {what_it_is}
Desired outcome: {outcome}
Storyboard: {build_storyline(job)}
Step details:
{chr(10).join(step_lines)}

Visual requirements:
- use a wide 16:9 landscape composition on a bright white or very light background
- keep the full composition centered with generous outer margins on all sides
- enforce a safe frame so no important content touches or crosses the image edges
- leave extra padding on the left and right edges to avoid cropped cards, icons, or arrows
- style should match a polished civic-tech / public-sector explainer board with cartoon illustration
- structure the image like a multi-panel operating model board: bold headline at top, short subhead, then a row of numbered colored panels
- each step should appear as its own vertical card or framed panel with a strong colored header, a large step number badge, and a focused illustrated scene
- connect the panels left-to-right with clear directional flow arrows
- use flat vector cartoon shapes with bold silhouettes, crisp outlines, and minimal shading
- use professional, friendly cartoon characters in realistic operational settings
- include simplified but legible product UI fragments, dashboards, forms, maps, signage, devices, and workflow artifacts
- include a small capability list or checklist area inside each panel
- add a bottom ribbon or summary strip showing outcomes, benefits, or KPI impact icons
- use saturated but disciplined blue, teal, and orange blocks similar to an executive explainer poster
- make it look like a structured explainer board, not a loose comic page, stock illustration, or generic infographic card
- balance whitespace evenly across the canvas, especially at the far left and far right
- ensure all cards, arrows, icons, and footer ribbons are fully visible inside the canvas
- no fantasy elements, no photorealism, no 3D render, no painterly style, no clutter, no text-heavy poster
- visually encode governance, process clarity, accountability, and measurable outcomes

Prompt inspiration:
{inspiration[:1600]}
""".strip()


def build_step_prompt(
    domain_id: str,
    customer_name: str,
    customer_description: str,
    job: dict[str, Any],
    step: dict[str, Any],
    step_index: int,
    inspiration: str,
) -> str:
    capability_summary = build_capability_summary(step)
    return f"""
Create one polished cartoon-style operating panel for a single job-to-be-done step.

Domain: {domain_id}
Customer: {customer_name}
Customer context: {customer_description}
Job to be done: {job.get("name", "")}
Job outcome: {job.get("outcome", "")}
Step number: {step_index}
Step title: {step.get("step", "")}
Step description: {step.get("description", "")}
Capabilities that must be visually grounded in the panel:
{capability_summary or "- No explicit capability mapping provided"}

Visual requirements:
- use a single framed cartoon panel on a bright white or very light background
- style should match a polished explainer-board panel rather than a loose comic drawing
- include a bold colored top header, large step number badge, concise caption area, and one main illustrated operating scene
- use flat vector cartoon shapes, crisp outlines, minimal shading, and strong visual hierarchy
- simple professional characters with expressive poses and clear action
- include just enough interface detail to explain the action
- include objects, dashboards, forms, maps, system signals, or workflow cues that reflect the named capabilities
- include a small checklist or capability box integrated into the panel
- use saturated but disciplined blue, teal, and orange accents unless the domain clearly demands otherwise
- visually distinct from other steps but stylistically consistent
- no fantasy elements, no photorealism, no 3D render, no clip-art, no random unrelated scenery

Prompt inspiration:
{inspiration[:1600]}
""".strip()


def title_for_job(customer_name: str, job_name: str) -> str:
    return f"{customer_name} JTBD infographic: {job_name}"


def alt_for_job(customer_name: str, job_name: str) -> str:
    return f"Enterprise infographic for the job \"{job_name}\" for customer \"{customer_name}\"."


def title_for_step(customer_name: str, job_name: str, step_name: str, step_index: int) -> str:
    return f"{customer_name} JTBD step {step_index}: {step_name}"


def alt_for_step(job_name: str, step_name: str, step_index: int) -> str:
    return f"Enterprise infographic for step {step_index} of the job \"{job_name}\": {step_name}."


def build_targets_for_file(
    path: Path,
    inspiration: str,
    output_format: str,
    lightweight: bool = False,
) -> tuple[list[GenerationTarget], Any]:
    payload = load_json(path)
    domain_id = path.parent.parent.name
    media_dir = path.parent / "media"
    targets: list[GenerationTarget] = []

    if not isinstance(payload, list):
        return targets, payload

    for group in payload:
        if not isinstance(group, dict):
            continue
        customers = group.get("customers") or []
        for customer in customers:
            if not isinstance(customer, dict):
                continue
            customer_id = str(customer.get("id") or slugify(str(customer.get("name") or ""), "cust"))
            customer_name = str(customer.get("name") or customer_id)
            customer_description = str(customer.get("description") or "")
            jobs = customer.get("jobsToBeDone") or []
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("id") or slugify(str(job.get("name") or ""), "job"))
                job_filename = make_job_filename(customer_id, job_id, output_format)
                job_media_src = f"media/{job_filename}"
                job_title = title_for_job(customer_name, str(job.get("name") or job_id))
                job_alt = alt_for_job(customer_name, str(job.get("name") or job_id))
                upsert_image_media(job, job_media_src, job_title, job_alt)
                targets.append(
                    GenerationTarget(
                        domain_id=domain_id,
                        customers_json_path=path,
                        customer_name=customer_name,
                        customer_description=customer_description,
                        customer_id=customer_id,
                        job=job,
                        step=None,
                        image_path=media_dir / job_filename,
                        media_src=job_media_src,
                        title=job_title,
                        alt=job_alt,
                        prompt=build_job_prompt(
                            domain_id, customer_name, customer_description, job, inspiration
                        ),
                        level="job",
                    )
                )

                if lightweight:
                    continue

                steps = job.get("steps") or []
                for step_index, step in enumerate(steps, start=1):
                    if not isinstance(step, dict):
                        continue
                    step_filename = make_step_filename(customer_id, job_id, step_index, output_format)
                    step_media_src = f"media/{step_filename}"
                    step_title = title_for_step(
                        customer_name,
                        str(job.get("name") or job_id),
                        str(step.get("step") or f"Step {step_index}"),
                        step_index,
                    )
                    step_alt = alt_for_step(
                        str(job.get("name") or job_id),
                        str(step.get("step") or f"Step {step_index}"),
                        step_index,
                    )
                    upsert_image_media(step, step_media_src, step_title, step_alt)
                    targets.append(
                        GenerationTarget(
                            domain_id=domain_id,
                            customers_json_path=path,
                            customer_name=customer_name,
                            customer_description=customer_description,
                            customer_id=customer_id,
                            job=job,
                            step=step,
                            image_path=media_dir / step_filename,
                            media_src=step_media_src,
                            title=step_title,
                            alt=step_alt,
                            prompt=build_step_prompt(
                                domain_id,
                                customer_name,
                                customer_description,
                                job,
                                step,
                                step_index,
                                inspiration,
                            ),
                            level="step",
                            step_index=step_index,
                        )
                    )

    return targets, payload


def payload_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def write_image(path: Path, image_bytes: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN image write: {path}")
        return
    path.write_bytes(image_bytes)


def validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)


def sync_target_media(
    target: GenerationTarget,
    output_format: str,
) -> bool:
    expected_name = (
        make_job_filename(target.customer_id, str(target.job.get("id") or ""), output_format)
        if target.level == "job"
        else make_step_filename(
            target.customer_id,
            str(target.job.get("id") or ""),
            int(target.step_index or 1),
            output_format,
        )
    )
    expected_src = f"media/{expected_name}"
    expected_path = target.image_path.with_suffix(f".{output_format}")
    changed = False

    if target.image_path != expected_path:
        target.image_path = expected_path
        changed = True

    if target.media_src != expected_src:
        target.media_src = expected_src
        changed = True

    if target.level == "job":
        changed = upsert_image_media(target.job, expected_src, target.title, target.alt) or changed
    elif target.step is not None:
        changed = upsert_image_media(target.step, expected_src, target.title, target.alt) or changed

    return changed


def run_generation(
    *,
    args: argparse.Namespace,
    api_key: str,
    api_key_label: str,
    generate_image: Callable[[str, GenerationTarget, argparse.Namespace], GeneratedImage],
) -> int:
    inspiration = load_prompt_inspiration()

    if not args.json_only and not args.dry_run and not api_key:
        print(f"{api_key_label} is required unless --json-only or --dry-run is used.", file=sys.stderr)
        return 2

    customer_files = list_customer_files(args.domain)
    if not customer_files:
        print("No customers.json files found for the selected scope.", file=sys.stderr)
        return 1

    total_generated = 0
    total_json_updates = 0

    for customer_file in customer_files:
        original_payload = load_json(customer_file)
        original_text = payload_text(original_payload)
        targets, payload = build_targets_for_file(
            customer_file,
            inspiration,
            args.output_format,
            lightweight=args.lightweight,
        )
        json_changed = payload_text(payload) != original_text

        for target in targets:
            json_changed = sync_target_media(target, args.output_format) or json_changed

            should_generate = not args.json_only
            if args.limit and total_generated >= args.limit:
                should_generate = False
            if args.skip_existing and target.image_path.exists():
                should_generate = False
            if target.image_path.exists() and not args.overwrite and not args.skip_existing:
                should_generate = False

            if should_generate:
                ensure_dir(target.image_path.parent, args.dry_run)
                print(f"Generating {target.level}: {target.image_path}")
                if not args.dry_run:
                    generated = generate_image(api_key, target, args)
                    actual_format = generated.output_format or args.output_format
                    if actual_format != args.output_format:
                        json_changed = sync_target_media(target, actual_format) or json_changed
                    write_image(target.image_path, generated.image_bytes, dry_run=False)
                else:
                    write_image(target.image_path, b"", dry_run=True)
                total_generated += 1
                if args.sleep_seconds > 0 and not args.dry_run:
                    time.sleep(args.sleep_seconds)
            else:
                print(f"Skipping {target.level}: {target.image_path}")

        if json_changed:
            dump_json(customer_file, payload, args.dry_run)
            if not args.dry_run:
                validate_json(customer_file)
            total_json_updates += 1

    print(
        f"Completed. Generated {total_generated} images and updated {total_json_updates} customers.json files."
    )
    return 0

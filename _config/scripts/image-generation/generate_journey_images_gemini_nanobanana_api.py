#!/usr/bin/env python3
"""Generate customer journey and journey-stage images via the Gemini Nano Banana image API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
sys.path.insert(0, str(REPO_ROOT / "_wiring"))
from project_paths import DOMAINS_ROOT as PRODUCT_DOMAINS_DIR, PROJECT_ROOT

from domain_paths import list_domain_files
PROMPT_INSPIRATION_PATH = SCRIPT_PATH.parent / "customer-journeys.md"
DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_QUALITY = "low"
DEFAULT_OUTPUT_FORMAT = "png"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)
MIME_TYPE_TO_FORMAT = {
    "image/png": "png"
}


@dataclass
class GeneratedImage:
    image_bytes: bytes
    output_format: str | None = None


@dataclass
class JourneyGenerationTarget:
    domain_id: str
    customers_json_path: Path
    customer_name: str
    customer_description: str
    customer_id: str
    journey: dict[str, Any]
    stage: dict[str, Any] | None
    image_path: Path
    media_src: str
    title: str
    alt: str
    prompt: str
    level: str
    stage_index: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate customer journey and stage images using the Gemini Nano Banana image API."
    )
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image-generation model.")
    parser.add_argument("--quality", default=DEFAULT_QUALITY, help="Image quality, if supported.")
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=("png",),
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
        help="Generate only one overview image per journey, without per-stage images.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between API calls.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="How many times to retry transient Gemini failures such as HTTP 500.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=5.0,
        help="Base delay before retrying transient Gemini failures.",
    )
    parser.add_argument(
        "--api-key-env",
        default="GEMINI_API_KEY",
        choices=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        help="Environment variable to read for the Gemini API key.",
    )
    return parser.parse_args()


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


def payload_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def write_image(path: Path, image_bytes: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN image write: {path}")
        return
    path.write_bytes(image_bytes)


def validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def journey_token(value: str) -> str:
    token = slugify(value, "journey")
    if token.startswith("journey-"):
        token = token[len("journey-"):]
    return token or "journey"


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


def make_journey_filename(customer_id: str, journey_id: str, output_format: str) -> str:
    return f"journey-{slugify(customer_id, 'cust')}-{journey_token(journey_id)}.{output_format}"


def make_stage_filename(
    customer_id: str,
    journey_id: str,
    stage_index: int,
    output_format: str,
) -> str:
    return (
        f"journey-{slugify(customer_id, 'cust')}-{journey_token(journey_id)}-{stage_index}.{output_format}"
    )


def stage_name(stage: dict[str, Any], stage_index: int) -> str:
    return str(stage.get("stage") or f"Stage {stage_index}")


def build_journey_storyline(journey: dict[str, Any]) -> str:
    labels: list[str] = []
    for index, stage in enumerate(journey.get("stages") or [], start=1):
        if not isinstance(stage, dict):
            continue
        labels.append(f"{index}. {stage_name(stage, index)}")
    return " | ".join(labels)


def build_journey_prompt(
    domain_id: str,
    customer_name: str,
    customer_description: str,
    journey: dict[str, Any],
    inspiration: str,
) -> str:
    stage_lines: list[str] = []
    for index, stage in enumerate(journey.get("stages") or [], start=1):
        if not isinstance(stage, dict):
            continue
        stage_lines.append(
            f"{index}. {stage_name(stage, index)}: {stage.get('narrative', '')}"
        )

    linked_jobs = ", ".join(journey.get("linkedJobIds") or [])

    return f"""
Create a single polished landscape explainer board for this customer journey story.

Domain: {domain_id}
Customer: {customer_name}
Customer context: {customer_description}
Journey story: {journey.get("name", "")}
Journey summary: {journey.get("summary", "")}
Linked jobs: {linked_jobs or "None provided"}
Stage flow: {build_journey_storyline(journey)}
Stage narratives:
{chr(10).join(stage_lines)}

Visual requirements:
- use a wide 16:9 landscape composition on a bright white or very light background
- present the journey as a polished operating-model storyboard with six connected stages from left to right
- each stage should appear as its own framed card with a strong label, one clear scene, and visual cues for the customer decision point
- include directional flow arrows so the reader can follow the full arc from trigger to retention
- show the same core customer across the journey with clear continuity in setting, product touchpoints, and stakes
- style should match a polished business explainer board with flat vector cartoon illustration, crisp outlines, and minimal shading
- include lightweight UI fragments, messages, dashboards, operational artifacts, or support touchpoints where they help explain the stage
- add a headline and short summary strip that make the journey feel like an intentional future-state vision rather than a generic infographic
- use disciplined blue, teal, green, and orange accents unless the domain clearly demands something else
- preserve generous margins so no card, arrow, or label touches the edges
- no photorealism, no 3D render, no fantasy elements, no clip-art collage, no dense text poster

Prompt inspiration:
{inspiration[:1600]}
""".strip()


def build_stage_prompt(
    domain_id: str,
    customer_name: str,
    customer_description: str,
    journey: dict[str, Any],
    stage: dict[str, Any],
    stage_index: int,
    inspiration: str,
) -> str:
    linked_jobs = ", ".join(journey.get("linkedJobIds") or [])
    return f"""
Create one polished cartoon-style operating panel for a single customer journey stage.

Domain: {domain_id}
Customer: {customer_name}
Customer context: {customer_description}
Journey story: {journey.get("name", "")}
Journey summary: {journey.get("summary", "")}
Linked jobs: {linked_jobs or "None provided"}
Stage number: {stage_index}
Stage name: {stage_name(stage, stage_index)}
Stage narrative: {stage.get("narrative", "")}

Visual requirements:
- use a single framed cartoon panel on a bright white or very light background
- style should match a polished business explainer panel rather than a loose comic drawing
- include a bold top header, strong stage number badge, short caption area, and one clear operating scene
- make the customer action, product touchpoint, and decision tension visually obvious at a glance
- include only the most relevant interface fragments, notifications, devices, forms, dashboards, maps, or support artifacts for this stage
- use flat vector cartoon shapes, crisp outlines, minimal shading, and strong visual hierarchy
- keep the composition clean, legible, and self-contained with generous padding
- use disciplined blue, teal, green, and orange accents unless the domain clearly demands something else
- no photorealism, no 3D render, no fantasy elements, no cluttered poster layout

Prompt inspiration:
{inspiration[:1600]}
""".strip()


def title_for_journey(customer_name: str, journey_name: str) -> str:
    return f"{customer_name} customer journey: {journey_name}"


def alt_for_journey(customer_name: str, journey_name: str) -> str:
    return f"Enterprise journey storyboard for \"{journey_name}\" for customer \"{customer_name}\"."


def title_for_stage(customer_name: str, journey_name: str, stage_label: str, stage_index: int) -> str:
    return f"{customer_name} journey stage {stage_index}: {stage_label}"


def alt_for_stage(journey_name: str, stage_label: str, stage_index: int) -> str:
    return f"Enterprise journey panel for stage {stage_index} of \"{journey_name}\": {stage_label}."


def build_targets_for_file(
    path: Path,
    inspiration: str,
    output_format: str,
    lightweight: bool = False,
) -> tuple[list[JourneyGenerationTarget], Any]:
    payload = load_json(path)
    domain_id = path.parent.parent.name
    media_dir = path.parent / "media"
    targets: list[JourneyGenerationTarget] = []

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
            journeys = customer.get("customerJourneyStories") or []
            for journey in journeys:
                if not isinstance(journey, dict):
                    continue
                journey_id = str(journey.get("id") or slugify(str(journey.get("name") or ""), "journey"))
                journey_filename = make_journey_filename(customer_id, journey_id, output_format)
                journey_media_src = f"media/{journey_filename}"
                journey_title = title_for_journey(customer_name, str(journey.get("name") or journey_id))
                journey_alt = alt_for_journey(customer_name, str(journey.get("name") or journey_id))
                upsert_image_media(journey, journey_media_src, journey_title, journey_alt)
                targets.append(
                    JourneyGenerationTarget(
                        domain_id=domain_id,
                        customers_json_path=path,
                        customer_name=customer_name,
                        customer_description=customer_description,
                        customer_id=customer_id,
                        journey=journey,
                        stage=None,
                        image_path=media_dir / journey_filename,
                        media_src=journey_media_src,
                        title=journey_title,
                        alt=journey_alt,
                        prompt=build_journey_prompt(
                            domain_id, customer_name, customer_description, journey, inspiration
                        ),
                        level="journey",
                    )
                )

                if lightweight:
                    continue

                stages = journey.get("stages") or []
                for stage_index, stage in enumerate(stages, start=1):
                    if not isinstance(stage, dict):
                        continue
                    stage_filename = make_stage_filename(customer_id, journey_id, stage_index, output_format)
                    stage_media_src = f"media/{stage_filename}"
                    stage_label = stage_name(stage, stage_index)
                    stage_title = title_for_stage(
                        customer_name,
                        str(journey.get("name") or journey_id),
                        stage_label,
                        stage_index,
                    )
                    stage_alt = alt_for_stage(
                        str(journey.get("name") or journey_id),
                        stage_label,
                        stage_index,
                    )
                    upsert_image_media(stage, stage_media_src, stage_title, stage_alt)
                    targets.append(
                        JourneyGenerationTarget(
                            domain_id=domain_id,
                            customers_json_path=path,
                            customer_name=customer_name,
                            customer_description=customer_description,
                            customer_id=customer_id,
                            journey=journey,
                            stage=stage,
                            image_path=media_dir / stage_filename,
                            media_src=stage_media_src,
                            title=stage_title,
                            alt=stage_alt,
                            prompt=build_stage_prompt(
                                domain_id,
                                customer_name,
                                customer_description,
                                journey,
                                stage,
                                stage_index,
                                inspiration,
                            ),
                            level="stage",
                            stage_index=stage_index,
                        )
                    )

    return targets, payload


def sync_target_media(target: JourneyGenerationTarget, output_format: str) -> bool:
    journey_id = str(target.journey.get("id") or "")
    if target.level == "journey":
        expected_name = make_journey_filename(target.customer_id, journey_id, output_format)
        changed = upsert_image_media(target.journey, f"media/{expected_name}", target.title, target.alt)
    else:
        expected_name = make_stage_filename(
            target.customer_id,
            journey_id,
            int(target.stage_index or 1),
            output_format,
        )
        changed = False
        if target.stage is not None:
            changed = upsert_image_media(target.stage, f"media/{expected_name}", target.title, target.alt)

    expected_src = f"media/{expected_name}"
    expected_path = target.image_path.with_suffix(f".{output_format}")

    if target.image_path != expected_path:
        target.image_path = expected_path
        changed = True
    if target.media_src != expected_src:
        target.media_src = expected_src
        changed = True
    return changed


def extract_generated_image(payload: dict[str, object], fallback_format: str) -> GeneratedImage:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(f"Unexpected Gemini response: {payload}")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        parts = content.get("parts") or []
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline_data = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline_data, dict):
                continue
            data = inline_data.get("data")
            mime_type = inline_data.get("mimeType") or inline_data.get("mime_type")
            if not isinstance(data, str):
                continue
            output_format = MIME_TYPE_TO_FORMAT.get(str(mime_type or "").lower(), fallback_format)
            return GeneratedImage(image_bytes=base64.b64decode(data), output_format=output_format)

    raise RuntimeError(f"Gemini response did not contain inline image data: {payload}")


def call_gemini_nanobanana_api(
    api_key: str,
    target: JourneyGenerationTarget,
    args: argparse.Namespace,
) -> GeneratedImage:
    request_url = API_URL_TEMPLATE.format(
        model=urllib.parse.quote(args.model, safe=""),
        api_key=urllib.parse.quote(api_key, safe=""),
    )
    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": target.prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        request_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    transient_status_codes = {500, 502, 503, 504}
    max_attempts = max(1, int(args.max_retries) + 1)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return extract_generated_image(payload, args.output_format)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Gemini API error {exc.code}: {detail}")
            if exc.code not in transient_status_codes or attempt == max_attempts:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"Network error while calling Gemini Nano Banana API: {exc}")
            if attempt == max_attempts:
                raise last_error from exc

        delay = float(args.retry_delay_seconds) * (2 ** (attempt - 1))
        print(
            f"Transient Gemini failure on attempt {attempt}/{max_attempts}. "
            f"Retrying in {delay:.1f}s for {target.level} {target.image_path.name}"
        )
        time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Gemini request failed without a captured error.")


def run_generation(args: argparse.Namespace, api_key: str) -> int:
    inspiration = load_prompt_inspiration()

    if not args.json_only and not args.dry_run and not api_key:
        print(f"{args.api_key_env} is required unless --json-only or --dry-run is used.", file=sys.stderr)
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
                    generated = call_gemini_nanobanana_api(api_key, target, args)
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
        f"Done. Generated {total_generated} image(s). Updated JSON in {total_json_updates} file(s)."
    )
    return 0


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    return run_generation(args, api_key)


if __name__ == "__main__":
    raise SystemExit(main())

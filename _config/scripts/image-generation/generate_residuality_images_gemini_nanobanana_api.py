#!/usr/bin/env python3
"""Generate one illustration per residuality stressor via the Gemini Nano Banana API."""

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
DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_OUTPUT_FORMAT = "png"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)
MIME_TYPE_TO_FORMAT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}


@dataclass
class GeneratedImage:
    image_bytes: bytes
    output_format: str | None = None


@dataclass
class ResidualityGenerationTarget:
    domain_id: str
    residuality_json_path: Path
    stressor_id: str
    stressor: dict[str, Any]
    image_path: Path
    media_src: str
    title: str
    alt: str
    prompt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one residuality stressor image using Gemini Nano Banana for each stressor."
    )
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image-generation model.")
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=("png", "jpg", "jpeg", "webp"),
        help="Image output format or preferred file extension.",
    )
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


def list_residuality_files(domain_filter: str | None) -> list[Path]:
    return list_domain_files("residuality/residuality.json", domain_filter, PRODUCT_DOMAINS_DIR)


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


def validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def make_stressor_filename(stressor_id: str, output_format: str) -> str:
    return f"stressor-{slugify(stressor_id, 'stressor')}.{output_format}"


def pick_image_media(media: Any) -> dict[str, Any] | None:
    if not isinstance(media, list):
        return None
    for entry in media:
        if isinstance(entry, dict) and entry.get("type") == "image":
            return entry
    return None


def upsert_image_media(stressor: dict[str, Any], media_src: str, title: str, alt: str) -> bool:
    media = stressor.get("media")
    if not isinstance(media, list):
        media = []
        stressor["media"] = media

    entry = pick_image_media(media)
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


def impact_summary(stressor: dict[str, Any]) -> str:
    lines: list[str] = []
    for impact in stressor.get("impacts") or []:
        if not isinstance(impact, dict):
            continue
        target_type = str(impact.get("targetType") or "object")
        target_id = str(impact.get("targetId") or "unknown")
        effect = str(impact.get("effect") or "")
        lines.append(f"- {target_type} {target_id}: {effect}")
    return "\n".join(lines)


def build_stressor_prompt(
    domain_id: str,
    metadata: dict[str, Any],
    stressor: dict[str, Any],
) -> str:
    reused_residues = ", ".join(str(value) for value in stressor.get("reusesResidueIds") or [])
    impacts = impact_summary(stressor)
    return f"""
Create one polished landscape editorial illustration for a residuality business-context stressor.

Domain: {domain_id}
Domain stress test: {metadata.get("title", "")}
Domain context: {metadata.get("description", "")}
Naive architecture: {metadata.get("naiveArchitecture", "")}
Residual architecture: {metadata.get("residualArchitecture", "")}

Stressor: {stressor.get("name", "")}
Business-context group: {stressor.get("group", "")}
How it is detected: {stressor.get("detection", "")}
Attractor state: {stressor.get("attractor", "")}
Business reaction: {stressor.get("businessReaction", "")}
Residue that must remain: {stressor.get("residue", "")}
Residue status: {stressor.get("status", "candidate")}
Earlier residues reused: {reused_residues or "None"}
Productscape impacts:
{impacts or "- No mapped impacts"}

Visual requirements:
- use a wide 16:9 landscape composition on a bright white or very light background
- tell one coherent left-to-right visual story: weak signals, the changed attractor state, the business response, and the resilient residue
- make the specific business-context disruption immediately recognizable; anchor every scene in this domain rather than using generic risk symbols
- show a clear contrast between the brittle starting assumption and the product or operating capability that survives the changed state
- use a polished business editorial style with flat vector illustration, crisp outlines, restrained shading, and strong visual hierarchy
- use disciplined amber for disruption, blue for deliberate response, and green or violet for the surviving residue
- use people, environments, product surfaces, operational artifacts, policy cues, and architecture motifs only when they clarify this exact stressor
- keep text minimal; at most use the four short labels Signal, Attractor, Response, and Residue
- preserve generous margins so all scenes, connectors, and important objects stay inside the canvas
- do not draw probability gauges, likelihood scales, risk matrices, percentages, or forecasts; residuality stressors deliberately carry no probability
- no photorealism, no 3D render, no fantasy spectacle, no clip-art collage, and no dense text poster
""".strip()


def build_targets_for_file(
    path: Path,
    output_format: str,
) -> tuple[list[ResidualityGenerationTarget], dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object in {path}")

    stressors = payload.get("stressors")
    if not isinstance(stressors, list):
        raise ValueError(f"Expected a stressors array in {path}")

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    domain_id = path.parents[1].name
    media_dir = path.parent / "media"
    targets: list[ResidualityGenerationTarget] = []

    for index, stressor in enumerate(stressors, start=1):
        if not isinstance(stressor, dict):
            continue
        stressor_id = str(stressor.get("id") or f"stressor-{index}")
        stressor_name = str(stressor.get("name") or stressor_id)
        filename = make_stressor_filename(stressor_id, output_format)
        image_path = media_dir / filename
        media_src = f"media/{filename}"

        image_media = pick_image_media(stressor.get("media"))
        existing_src = image_media.get("src") if image_media else None
        if isinstance(existing_src, str):
            relative_src = Path(existing_src)
            existing_path = path.parent / relative_src
            if (
                not relative_src.is_absolute()
                and ".." not in relative_src.parts
                and existing_path.is_file()
                and existing_path.stem == Path(filename).stem
            ):
                image_path = existing_path
                media_src = existing_src

        targets.append(
            ResidualityGenerationTarget(
                domain_id=domain_id,
                residuality_json_path=path,
                stressor_id=stressor_id,
                stressor=stressor,
                image_path=image_path,
                media_src=media_src,
                title=f"Residuality stressor illustration: {stressor_name}",
                alt=(
                    f"Illustration of the residuality stressor '{stressor_name}', showing its "
                    "signal, attractor, business response, and surviving residue."
                ),
                prompt=build_stressor_prompt(domain_id, metadata, stressor),
            )
        )

    return targets, payload


def sync_target_media(target: ResidualityGenerationTarget, output_format: str) -> bool:
    filename = make_stressor_filename(target.stressor_id, output_format)
    target.image_path = target.image_path.with_name(filename)
    target.media_src = f"media/{filename}"
    return upsert_image_media(target.stressor, target.media_src, target.title, target.alt)


def extract_generated_image(payload: dict[str, Any], fallback_format: str) -> GeneratedImage:
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
    target: ResidualityGenerationTarget,
    args: argparse.Namespace,
) -> GeneratedImage:
    request_url = API_URL_TEMPLATE.format(
        model=urllib.parse.quote(args.model, safe=""),
        api_key=urllib.parse.quote(api_key, safe=""),
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": target.prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
    ).encode("utf-8")

    transient_status_codes = {500, 502, 503, 504}
    max_attempts = max(1, int(args.max_retries) + 1)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            request_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            return extract_generated_image(response_payload, args.output_format)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Gemini API error {exc.code}: {detail}")
            if exc.code not in transient_status_codes or attempt == max_attempts:
                raise last_error from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = RuntimeError(f"Network error while calling Gemini Nano Banana API: {exc}")
            if attempt == max_attempts:
                raise last_error from exc

        delay = float(args.retry_delay_seconds) * (2 ** (attempt - 1))
        print(
            f"Transient Gemini failure on attempt {attempt}/{max_attempts}. "
            f"Retrying in {delay:.1f}s for {target.image_path.name}"
        )
        time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Gemini request failed without a captured error.")


def should_generate_target(
    target: ResidualityGenerationTarget,
    args: argparse.Namespace,
    generated_count: int,
) -> bool:
    if args.json_only:
        return False
    if args.limit and generated_count >= args.limit:
        return False
    if target.image_path.exists() and args.skip_existing:
        return False
    if target.image_path.exists() and not args.overwrite:
        return False
    return True


def run_generation(args: argparse.Namespace, api_key: str) -> int:
    residuality_files = list_residuality_files(args.domain)
    if not residuality_files:
        print("No residuality.json files found for the selected scope; nothing to generate.")
        return 0

    if not args.json_only and not args.dry_run and not api_key:
        print(f"{args.api_key_env} is required unless --json-only or --dry-run is used.", file=sys.stderr)
        return 2

    total_generated = 0
    total_json_updates = 0

    for residuality_file in residuality_files:
        targets, payload = build_targets_for_file(residuality_file, args.output_format)
        json_changed = False

        for target in targets:
            image_exists = target.image_path.exists()
            existing_format = target.image_path.suffix.lstrip(".") or args.output_format
            should_generate = should_generate_target(target, args, total_generated)

            if should_generate:
                print(f"Generating stressor: {target.image_path}")
                if args.dry_run:
                    print(f"DRY RUN image write: {target.image_path}")
                    json_changed = sync_target_media(target, args.output_format) or json_changed
                else:
                    target.image_path.parent.mkdir(parents=True, exist_ok=True)
                    generated = call_gemini_nanobanana_api(api_key, target, args)
                    actual_format = generated.output_format or args.output_format
                    json_changed = sync_target_media(target, actual_format) or json_changed
                    target.image_path.write_bytes(generated.image_bytes)
                total_generated += 1
                if args.sleep_seconds > 0 and not args.dry_run:
                    time.sleep(args.sleep_seconds)
            else:
                print(f"Skipping stressor: {target.image_path}")

            if args.json_only or image_exists:
                reference_format = existing_format if image_exists else args.output_format
                json_changed = sync_target_media(target, reference_format) or json_changed

        if json_changed:
            dump_json(residuality_file, payload, args.dry_run)
            if not args.dry_run:
                validate_json(residuality_file)
            total_json_updates += 1

    print(
        f"Done. Generated {total_generated} image(s). Updated JSON in {total_json_updates} file(s)."
    )
    return 0


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    try:
        return run_generation(args, api_key)
    except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

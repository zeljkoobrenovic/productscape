#!/usr/bin/env python3
"""Generate rich customer-role illustrations for the existing customer icon field.

Uses the friendly cartoon character style of the customer-relations overview,
with a square composition suited to customer cards and landing pages. Writes
customers/icons/customer-<id>-portrait.<format> and updates customers.json only
after an image exists. Legacy icons, customer media, and generated docs are kept.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
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
DEFAULT_MAX_RETRIES = 4
DEFAULT_RETRY_DELAY_SECONDS = 5.0
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)
MIME_TYPE_TO_FORMAT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}
IMAGE_FORMATS = ("png", "jpg", "jpeg", "webp")


@dataclass
class GeneratedImage:
    image_bytes: bytes
    output_format: str


@dataclass
class CustomerIconTarget:
    customer: dict[str, Any]
    image_path: Path
    prompt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate rich customer icons in the cartoon style of customer-relations images."
    )
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--customer", help="Only process this customer id within the selected domains.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate; 0 means all.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini image-generation model.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files or calling the API.")
    parser.add_argument("--json-only", action="store_true", help="Link existing portraits only; call no API.")
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument("--skip-existing", action="store_true", help="Skip existing portraits (the default).")
    existing.add_argument("--overwrite", action="store_true", help="Regenerate existing portraits.")
    parser.add_argument(
        "--api-key-env",
        default="GEMINI_API_KEY",
        choices=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        help="Environment variable to read for the Gemini API key.",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retries for transient API failures.")
    parser.add_argument("--retry-delay-seconds", type=float, default=DEFAULT_RETRY_DELAY_SECONDS, help="Base retry delay.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Pause between generated images.")
    args = parser.parse_args()
    for name in ("limit", "max_retries", "retry_delay_seconds", "sleep_seconds"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be nonnegative")
    return args


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_bytes(path: Path, data: bytes) -> None:
    """Replace a file only after its complete contents have been written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    permissions = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary_path = Path(handle.name)
        try:
            handle.write(data)
            handle.close()
            temporary_path.chmod(permissions)
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def image_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def make_customer_icon_filename(customer_id: str, output_format: str = "png") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", customer_id.lower()).strip("-")
    if not slug:
        raise ValueError(f"Customer id cannot form an icon filename: {customer_id!r}")
    return f"customer-{slug}-portrait.{output_format}"


def build_relations_summary(customer_id: str, relations: dict[str, Any], names: dict[str, str]) -> str:
    lines = []
    for relation in relations.get("relations", []) or []:
        if not isinstance(relation, dict) or customer_id not in (relation.get("from"), relation.get("to")):
            continue
        from_name = names.get(relation.get("from"), str(relation.get("from") or ""))
        to_name = names.get(relation.get("to"), str(relation.get("to") or ""))
        lines.append(
            f"- {from_name} -> {to_name}: {relation.get('name', '')}. "
            f"{str(relation.get('description') or '')[:200]}"
        )
    return "\n".join(lines[:6])


def build_customer_prompt(
    domain_name: str,
    domain_description: str,
    customer: dict[str, Any],
    group_name: str = "",
    relations_summary: str = "",
) -> str:
    jobs = []
    for job in (customer.get("jobsToBeDone") or [])[:3]:
        if isinstance(job, dict):
            jobs.append(f"- {job.get('name', '')}: {str(job.get('outcome') or job.get('what_it_is') or '')[:240]}")

    def summarize(key: str) -> str:
        values = customer.get(key) or []
        if isinstance(values, list):
            return "; ".join(str(value) for value in values[:4])
        return str(values)

    return f"""
Create one rich, friendly customer-role illustration for a product-strategy customer card.
Use the same character treatment as a customer-relations ecosystem explainer: an expressive
illustrated person with meaningful clothing, a natural working pose, and recognizable role-specific props.

Domain: {domain_name}
Domain context: {domain_description[:800]}
Customer group: {group_name}
Customer: {customer.get("name", customer.get("id", ""))}
Customer context: {str(customer.get("description") or "")[:1200]}
What they care about: {summarize("careAbout")}
What wins them over: {summarize("winsThem")}
What they fear: {summarize("theirFear")}
Main jobs and desired outcomes:
{chr(10).join(jobs) or "Use the customer context above."}
Role in the customer ecosystem:
{relations_summary or "Use the customer context above."}

Visual requirements:
- use a square 1:1 composition on a bright white or very light background
- match a polished business explainer board: flat vector cartoon illustration, crisp outlines, minimal shading
- use disciplined blue, teal, green, and orange accents, with natural skin tones
- make a friendly, professional character the main subject, with a clear face, readable hands, and a distinctive silhouette
- show the person from the waist up or in a compact working scene, large enough to remain recognizable at thumbnail size
- communicate this specific role through clothing, posture, and two or three meaningful tools, objects, or setting details grounded in the context
- for a team or organization, use at most two representative people; for a non-human stakeholder, depict its real subject faithfully
- use an inclusive cast and avoid caricatures or stereotyped gender assignments to professions
- include a small hint of the actual setting, with foreground and background separation; keep detail focused around the character
- convey customer needs through the scene, without turning fears or outcomes into extra panels or a diagram
- keep the full subject centered with generous safe margins; faces, hands, and props must stay inside the square and remain visible in a circular crop
- no text, letters, labels, logos, numbers, headline, legend, arrows, card border, or frame
- no monochrome line-art pictogram, generic anonymous avatar, clip-art collage, photorealism, 3D render, or fantasy elements
""".strip()


def build_targets_for_file(
    path: Path, payload: Any, customer_filter: str | None = None
) -> list[CustomerIconTarget]:
    if not isinstance(payload, list):
        raise ValueError(f"Expected an array of customer groups in {path}")
    domain_dir = path.parents[1]
    config_path = domain_dir / "start" / "config.json"
    config = load_json(config_path) if config_path.is_file() else {}
    relations_path = path.parent / "relations.json"
    relations = load_json(relations_path) if relations_path.is_file() else {}
    names = {
        customer.get("id"): str(customer.get("name") or customer.get("id") or "")
        for group in payload if isinstance(group, dict)
        for customer in group.get("customers", []) or [] if isinstance(customer, dict)
    }
    targets = []
    filenames: set[str] = set()
    for group in payload:
        if not isinstance(group, dict):
            continue
        for customer in group.get("customers", []) or []:
            if not isinstance(customer, dict):
                continue
            customer_id = str(customer.get("id") or "").strip()
            filename = make_customer_icon_filename(customer_id)
            if filename in filenames:
                raise ValueError(f"Customers resolve to the same portrait filename {filename!r} in {path}")
            filenames.add(filename)
            if customer_filter and customer_id != customer_filter:
                continue
            image_path = path.parent / "icons" / filename
            # Reuse portraits even when Gemini returned a format other than PNG,
            # including an image saved by an interrupted run before JSON was updated.
            candidates = [image_path.with_suffix(f".{fmt}") for fmt in IMAGE_FORMATS]
            current_name = customer.get("icon")
            if isinstance(current_name, str) and current_name in [candidate.name for candidate in candidates]:
                candidates.insert(0, image_path.with_name(current_name))
            image_path = next((candidate for candidate in candidates if image_exists(candidate)), image_path)
            targets.append(CustomerIconTarget(
                customer=customer,
                image_path=image_path,
                prompt=build_customer_prompt(
                    str(config.get("name") or domain_dir.name),
                    str(config.get("description") or ""),
                    customer,
                    str(group.get("group") or ""),
                    build_relations_summary(customer_id, relations, names),
                ),
            ))
    return targets


def extract_generated_image(payload: dict[str, Any]) -> GeneratedImage:
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        for part in (candidate.get("content") or {}).get("parts") or []:
            if not isinstance(part, dict) or part.get("thought"):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "").lower()
            output_format = MIME_TYPE_TO_FORMAT.get(mime_type)
            data = inline.get("data")
            if output_format and isinstance(data, str) and data:
                image_bytes = base64.b64decode(data, validate=True)
                if image_bytes:
                    return GeneratedImage(image_bytes, output_format)
    raise RuntimeError("Gemini response did not contain a supported inline image (PNG, JPEG, or WebP).")


def call_gemini_nanobanana_api(
    api_key: str, target: CustomerIconTarget, args: argparse.Namespace
) -> GeneratedImage:
    request_url = API_URL_TEMPLATE.format(
        model=urllib.parse.quote(args.model, safe=""),
        api_key=urllib.parse.quote(api_key, safe=""),
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": target.prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "1:1", "imageSize": "1K"},
        },
    }).encode("utf-8")
    max_attempts = max(1, int(getattr(args, "max_retries", DEFAULT_MAX_RETRIES)) + 1)
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            request_url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return extract_generated_image(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code not in {429, 500, 502, 503, 504} or attempt == max_attempts:
                raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            if attempt == max_attempts:
                raise RuntimeError(f"Network error while calling Gemini Nano Banana API: {exc}") from exc
        delay = float(getattr(args, "retry_delay_seconds", DEFAULT_RETRY_DELAY_SECONDS)) * (2 ** (attempt - 1))
        print(f"Transient Gemini failure on attempt {attempt}/{max_attempts}; retrying in {delay:.1f}s for {target.image_path.name}")
        time.sleep(delay)
    raise RuntimeError("Gemini request failed without a captured error.")


def generate_icons_for_file(
    path: Path, args: argparse.Namespace, api_key: str, generated_count: int = 0
) -> tuple[int, bool]:
    """Generate/link customer portraits, sharing the caller's overall image budget."""
    payload = load_json(path)
    targets = build_targets_for_file(path, payload, getattr(args, "customer", None))
    generated = 0
    json_changed = False
    for target in targets:
        should_generate = (
            not args.json_only
            and (not args.limit or generated_count + generated < args.limit)
            and (not image_exists(target.image_path) or (args.overwrite and not args.skip_existing))
        )
        if should_generate:
            print(f"Generating customer portrait: {target.image_path}")
            if args.dry_run:
                print(f"DRY RUN image write: {target.image_path}")
            else:
                image = call_gemini_nanobanana_api(api_key, target, args)
                target.image_path = target.image_path.with_suffix(f".{image.output_format}")
                # Preserve the illustration's filled whites, colors, and safe margins.
                # The monochrome icon generator's transparency/crop pass is unsuitable here.
                write_bytes(target.image_path, image.image_bytes)
            generated += 1
        else:
            print(f"Skipping customer portrait: {target.image_path}")

        if image_exists(target.image_path) or (args.dry_run and should_generate):
            if target.customer.get("icon") != target.image_path.name:
                target.customer["icon"] = target.image_path.name
                json_changed = True
                if not args.dry_run:
                    # Save each successful result so a later API failure loses no references.
                    write_bytes(path, (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        if should_generate and args.sleep_seconds > 0 and not args.dry_run:
            time.sleep(args.sleep_seconds)

    if args.dry_run and json_changed:
        print(f"DRY RUN json update: {path}")
    return generated, json_changed


def run_generation(args: argparse.Namespace, api_key: str) -> int:
    files = list_domain_files("customers/customers.json", args.domain, PRODUCT_DOMAINS_DIR)
    if not files:
        print("No customers.json files found for the selected scope.", file=sys.stderr)
        return 1
    if args.customer:
        files = [path for path in files if any(
            customer.get("id") == args.customer
            for group in load_json(path) if isinstance(group, dict)
            for customer in group.get("customers", []) or [] if isinstance(customer, dict)
        )]
        if not files:
            print(f"No customer with id {args.customer!r} found for the selected scope.", file=sys.stderr)
            return 1
    if not args.json_only and not args.dry_run and not api_key:
        print(f"{args.api_key_env} is required unless --json-only or --dry-run is used.", file=sys.stderr)
        return 2
    generated = 0
    json_updates = 0
    for path in files:
        count, changed = generate_icons_for_file(path, args, api_key, generated)
        generated += count
        json_updates += int(changed)
    print(f"Done. Generated {generated} customer portrait(s). Updated JSON in {json_updates} file(s).")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run_generation(args, os.environ.get(args.api_key_env, "").strip())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

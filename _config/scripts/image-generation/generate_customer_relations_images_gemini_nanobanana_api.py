#!/usr/bin/env python3
"""Generate one customer-relations overview illustration per domain via the Gemini Nano Banana image API.

Reads each domain's customers/relations.json (customer-to-customer relations),
builds a single network-style explainer illustration in the same cartoon style
as the JTBD and journey images, writes it into customers/media/, and patches a
top-level `media` entry into relations.json so the customers page can show it
at the top of the Relations tab.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
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
PROMPT_INSPIRATION_PATHS = [
    SCRIPT_PATH.parent / "customer-journeys.md",
    SCRIPT_PATH.parent / "customer-journeys.md",
]
DEFAULT_MODEL = "gemini-3-pro-image-preview"
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
class RelationsGenerationTarget:
    domain_id: str
    relations_json_path: Path
    image_path: Path
    media_src: str
    title: str
    alt: str
    prompt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate customer-relations overview images using the Gemini Nano Banana image API."
    )
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image-generation model.")
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT, help="Image file format.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument("--json-only", action="store_true", help="Only patch media references; call no API.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip images that already exist on disk.")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate images even if they exist.")
    parser.add_argument(
        "--api-key-env",
        default="GEMINI_API_KEY",
        choices=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        help="Environment variable to read for the Gemini API key.",
    )
    parser.add_argument("--max-retries", type=int, default=4, help="Retries for transient Gemini failures.")
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0, help="Base retry delay.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Pause between generated images.")
    return parser.parse_args()


def load_prompt_inspiration() -> str:
    for path in PROMPT_INSPIRATION_PATHS:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def list_relations_files(domain_filter: str | None) -> list[Path]:
    return list_domain_files("customers/relations.json", domain_filter, PRODUCT_DOMAINS_DIR)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN json update: {path}")
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_image(path: Path, image_bytes: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN image write: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)


def customer_names_by_id(domain_dir: Path) -> dict[str, dict[str, str]]:
    customers_path = domain_dir / "customers" / "customers.json"
    lookup: dict[str, dict[str, str]] = {}
    if not customers_path.exists():
        return lookup
    for group in load_json(customers_path):
        for customer in group.get("customers", []) or []:
            lookup[customer.get("id")] = {
                "name": customer.get("name", customer.get("id", "")),
                "group": group.get("group", ""),
                "description": customer.get("description", ""),
            }
    return lookup


def build_relations_prompt(
    domain_id: str,
    relations_payload: dict[str, Any],
    customers: dict[str, dict[str, str]],
    inspiration: str,
) -> str:
    role_lines = []
    for customer_id, info in customers.items():
        role_lines.append(f"- {info['name']} ({info['group']}): {info['description'][:160]}")

    type_lookup = {t.get("id"): t.get("name", t.get("id")) for t in relations_payload.get("relationTypes", [])}
    relation_lines = []
    for relation in relations_payload.get("relations", []) or []:
        from_name = customers.get(relation.get("from"), {}).get("name", relation.get("from"))
        to_name = customers.get(relation.get("to"), {}).get("name", relation.get("to"))
        type_name = type_lookup.get(relation.get("type"), relation.get("type"))
        relation_lines.append(
            f"- {from_name} -> {to_name} [{type_name}]: {relation.get('name', '')} — {relation.get('description', '')[:160]}"
        )

    return f"""
Create a single polished landscape explainer illustration of how the customer roles of a product ecosystem relate to each other.

Domain: {domain_id}
Ecosystem summary: {relations_payload.get("description", "")}

Customer roles (the nodes of the network):
{chr(10).join(role_lines)}

Relations between roles (the arrows of the network):
{chr(10).join(relation_lines)}

Visual requirements:
- use a wide 16:9 landscape composition on a bright white or very light background
- present the ecosystem as a relationship map: each customer role as a friendly illustrated character in a framed node card with a short label, arranged around the canvas
- connect the role cards with clearly directional arrows; differentiate relation kinds (commercial, operational, financial, information) by arrow color or line style, with a small legend
- keep every arrow attached to the two roles it connects; do not draw arrows into empty space
- show small pictorial cues on the arrows or beside them (contracts, trucks or goods, coins or invoices, charts or signals) matching the relation kind
- style should match a polished business explainer board with flat vector cartoon illustration, crisp outlines, and minimal shading
- add a short headline strip naming the ecosystem so the board reads as an intentional overview, not a generic diagram
- use disciplined blue, teal, green, and orange accents unless the domain clearly demands something else
- preserve generous margins so no card, arrow, or label touches the edges
- keep text minimal: role labels, a headline, and a small legend only; no dense paragraphs
- no photorealism, no 3D render, no fantasy elements, no clip-art collage

Prompt inspiration:
{inspiration[:1600]}
""".strip()


def upsert_media(payload: dict[str, Any], media_src: str, title: str, alt: str) -> bool:
    media = payload.get("media")
    if not isinstance(media, list):
        media = []
        payload["media"] = media
    for entry in media:
        if isinstance(entry, dict) and entry.get("type") == "image":
            changed = entry.get("src") != media_src or entry.get("title") != title or entry.get("alt") != alt
            entry.update({"src": media_src, "title": title, "alt": alt})
            return changed
    media.append({"type": "image", "src": media_src, "title": title, "alt": alt})
    return True


def build_target(relations_path: Path, inspiration: str, output_format: str) -> RelationsGenerationTarget | None:
    domain_dir = relations_path.parents[1]
    domain_id = domain_dir.name
    payload = load_json(relations_path)
    if not payload.get("relations"):
        return None
    customers = customer_names_by_id(domain_dir)
    filename = f"relations-overview.{output_format}"
    return RelationsGenerationTarget(
        domain_id=domain_id,
        relations_json_path=relations_path,
        image_path=domain_dir / "customers" / "media" / filename,
        media_src=f"media/{filename}",
        title=f"How the customers of {domain_id} relate to each other",
        alt=f"Illustrated relationship map of the customer roles in the {domain_id} domain.",
        prompt=build_relations_prompt(domain_id, payload, customers, inspiration),
    )


def extract_generated_image(payload: dict[str, Any], fallback_format: str) -> GeneratedImage:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(f"Unexpected Gemini response: {payload}")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for part in ((candidate.get("content") or {}).get("parts") or []):
            inline = part.get("inlineData") if isinstance(part, dict) else None
            if not isinstance(inline, dict) or "data" not in inline:
                continue
            image_bytes = base64.b64decode(inline["data"])
            mime_type = inline.get("mimeType", "")
            return GeneratedImage(
                image_bytes=image_bytes,
                output_format=MIME_TYPE_TO_FORMAT.get(mime_type, fallback_format),
            )
    raise RuntimeError(f"No image data in Gemini response: {json.dumps(payload)[:500]}")


def call_gemini_nanobanana_api(
    api_key: str,
    target: RelationsGenerationTarget,
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
                payload = json.loads(response.read().decode("utf-8"))
            return extract_generated_image(payload, args.output_format)
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


def run_generation(args: argparse.Namespace, api_key: str) -> int:
    inspiration = load_prompt_inspiration()

    if not args.json_only and not args.dry_run and not api_key:
        print(f"{args.api_key_env} is required unless --json-only or --dry-run is used.", file=sys.stderr)
        return 2

    relations_files = list_relations_files(args.domain)
    if not relations_files:
        print("No relations.json files found for the selected scope.", file=sys.stderr)
        return 1

    total_generated = 0
    total_json_updates = 0

    for relations_file in relations_files:
        target = build_target(relations_file, inspiration, args.output_format)
        if target is None:
            print(f"Skipping (no relations): {relations_file}")
            continue

        should_generate = not args.json_only
        if args.limit and total_generated >= args.limit:
            should_generate = False
        if args.skip_existing and target.image_path.exists():
            should_generate = False
        if target.image_path.exists() and not args.overwrite and not args.skip_existing:
            should_generate = False

        if should_generate:
            print(f"Generating relations overview: {target.image_path}")
            if not args.dry_run:
                generated = call_gemini_nanobanana_api(api_key, target, args)
                actual_format = generated.output_format or args.output_format
                if actual_format != args.output_format:
                    filename = f"relations-overview.{actual_format}"
                    target.image_path = target.image_path.with_name(filename)
                    target.media_src = f"media/{filename}"
                write_image(target.image_path, generated.image_bytes, dry_run=False)
            else:
                write_image(target.image_path, b"", dry_run=True)
            total_generated += 1
            if args.sleep_seconds > 0 and not args.dry_run:
                time.sleep(args.sleep_seconds)
        else:
            print(f"Skipping relations overview: {target.image_path}")

        # Only reference the image once it exists on disk (or would in a dry run),
        # so domains without a generated overview never point at a missing file.
        if target.image_path.exists() or (args.dry_run and should_generate):
            payload = load_json(target.relations_json_path)
            if upsert_media(payload, target.media_src, target.title, target.alt):
                dump_json(target.relations_json_path, payload, args.dry_run)
                total_json_updates += 1

    print(f"Done. Generated {total_generated} image(s). Updated JSON in {total_json_updates} file(s).")
    return 0


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    return run_generation(args, api_key)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate missing customer, KPI, start-page, product-brick, and product-capability icons via Gemini Nano Banana."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from generate_customer_icons_gemini_nanobanana_api import generate_icons_for_file


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
sys.path.insert(0, str(REPO_ROOT / "_wiring"))
from project_paths import DOMAINS_ROOT as PRODUCT_DOMAINS_DIR, PROJECT_ROOT

from domain_paths import discover_domain_dirs, resolve_domain_dir
DEFAULT_MODEL = "gemini-3-pro-image-preview"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)
OUTPUT_FORMAT = "png"
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
FFMPEG_PATH = shutil.which("ffmpeg") or ""
FFPROBE_PATH = shutil.which("ffprobe") or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate missing customer, start-page, product-brick, and product-capability icons with Gemini Nano Banana."
    )
    parser.add_argument("--domain", help="Only process one domain id.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of icons to generate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini image-generation model.")
    parser.add_argument(
        "--api-key-env",
        default="GEMINI_API_KEY",
        choices=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        help="Environment variable to read for the Gemini API key.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip generation if the target file already exists.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate icon files even when they already exist.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Update icon references only, without calling the API; customer portraits must already exist.",
    )
    parser.add_argument(
        "--skip-customer-icons",
        action="store_true",
        help="Leave customer portraits to the dedicated generator; still process customer KPI icons.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between API calls.",
    )
    return parser.parse_args()


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


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def write_image(path: Path, image_bytes: bytes, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN image write: {path}")
        return
    path.write_bytes(image_bytes)


def require_media_tools() -> None:
    if not FFMPEG_PATH or not FFPROBE_PATH:
        raise RuntimeError(
            "ffmpeg and ffprobe are required for icon post-processing but were not found on PATH."
        )


def probe_image_size(path: Path) -> tuple[int, int]:
    require_media_tools()
    result = subprocess.run(
        [
            FFPROBE_PATH,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError(f"Could not determine image dimensions for {path}.")
    stream = streams[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid image dimensions for {path}: {width}x{height}.")
    return width, height


def decode_to_rgba(path: Path, width: int, height: int) -> bytearray:
    require_media_tools()
    result = subprocess.run(
        [
            FFMPEG_PATH,
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    expected_len = width * height * 4
    if len(result.stdout) != expected_len:
        raise RuntimeError(
            f"Decoded RGBA buffer has unexpected size {len(result.stdout)}; expected {expected_len}."
        )
    return bytearray(result.stdout)


def find_crop_bounds(rgba: bytearray, width: int, height: int) -> tuple[int, int, int, int]:
    left = width
    right = -1
    top = height
    bottom = -1
    for y in range(height):
        row_offset = y * width * 4
        for x in range(width):
            idx = row_offset + x * 4
            if rgba[idx + 3] == 0:
                continue
            if x < left:
                left = x
            if x > right:
                right = x
            if y < top:
                top = y
            if y > bottom:
                bottom = y
    if right < left or bottom < top:
        return 0, 0, width, height
    pad = 1
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width - 1, right + pad)
    bottom = min(height - 1, bottom + pad)
    return left, top, right - left + 1, bottom - top + 1


def crop_rgba(
    rgba: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    crop_w: int,
    crop_h: int,
) -> bytes:
    rows: list[bytes] = []
    stride = width * 4
    for row in range(y, y + crop_h):
        start = row * stride + x * 4
        end = start + crop_w * 4
        rows.append(bytes(rgba[start:end]))
    return b"".join(rows)


def pad_rgba_to_aspect_ratio(
    rgba_bytes: bytes,
    width: int,
    height: int,
    target_ratio: float,
) -> tuple[bytes, int, int]:
    if target_ratio <= 0:
        return rgba_bytes, width, height

    current_ratio = width / height if height else target_ratio
    if abs(current_ratio - target_ratio) < 0.0001:
        return rgba_bytes, width, height

    if current_ratio > target_ratio:
        canvas_w = width
        canvas_h = max(height, int(round(width / target_ratio)))
    else:
        canvas_h = height
        canvas_w = max(width, int(round(height * target_ratio)))

    canvas = bytearray(canvas_w * canvas_h * 4)
    offset_x = max(0, (canvas_w - width) // 2)
    offset_y = max(0, (canvas_h - height) // 2)
    src_stride = width * 4
    dst_stride = canvas_w * 4

    for row in range(height):
        src_start = row * src_stride
        src_end = src_start + src_stride
        dst_start = (row + offset_y) * dst_stride + offset_x * 4
        dst_end = dst_start + src_stride
        canvas[dst_start:dst_end] = rgba_bytes[src_start:src_end]

    return bytes(canvas), canvas_w, canvas_h


def encode_rgba_to_png(rgba_bytes: bytes, width: int, height: int) -> bytes:
    require_media_tools()
    result = subprocess.run(
        [
            FFMPEG_PATH,
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgba",
            "-video_size",
            f"{width}x{height}",
            "-i",
            "pipe:0",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ],
        check=True,
        input=rgba_bytes,
        capture_output=True,
    )
    return result.stdout


def postprocess_icon_bytes(image_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="jtbd-icon-post-") as temp_dir:
        input_path = Path(temp_dir) / "input"
        input_path.write_bytes(image_bytes)
        width, height = probe_image_size(input_path)
        target_ratio = width / height if height else 1.0
        rgba = decode_to_rgba(input_path, width, height)

        for idx in range(0, len(rgba), 4):
            r = rgba[idx]
            g = rgba[idx + 1]
            b = rgba[idx + 2]
            a = rgba[idx + 3]
            if a == 0:
                continue
            if r >= 245 and g >= 245 and b >= 245:
                rgba[idx + 3] = 0

        x, y, crop_w, crop_h = find_crop_bounds(rgba, width, height)
        cropped = crop_rgba(rgba, width, height, x, y, crop_w, crop_h)
        padded, final_w, final_h = pad_rgba_to_aspect_ratio(
            cropped,
            crop_w,
            crop_h,
            target_ratio,
        )
        return encode_rgba_to_png(padded, final_w, final_h)


def list_domains(domain_filter: str | None) -> list[Path]:
    if domain_filter:
        return [resolve_domain_dir(domain_filter, PRODUCT_DOMAINS_DIR)]
    return discover_domain_dirs(PRODUCT_DOMAINS_DIR)


def normalize_icon_filename(value: str | None, fallback_stem: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return f"{fallback_stem}.{OUTPUT_FORMAT}"
    filename = Path(cleaned).name
    if "." not in filename:
        filename = f"{filename}.{OUTPUT_FORMAT}"
    return filename


def slugify(value: str | None) -> str:
    chars: list[str] = []
    last_dash = False
    for ch in (value or "").strip().lower():
        if ch.isalnum():
            chars.append(ch)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-") or "item"


def flatten_product_bricks(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "group":
            for child in node.get("children", []) or []:
                if isinstance(child, dict):
                    walk(child)
            return
        flat.append(node)

    for node in nodes:
        if isinstance(node, dict):
            walk(node)
    return flat


def collect_bricks(payload: Any) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []

    def walk_group(group: Any) -> None:
        if not isinstance(group, dict):
            return
        for brick in group.get("bricks", []) or []:
            if isinstance(brick, dict):
                flat.append(brick)
        for subgroup in group.get("subGroups", []) or []:
            walk_group(subgroup)

    if not isinstance(payload, dict):
        return flat

    # Support both legacy flat schemas and the current rootGroups/subGroups structure.
    flat.extend(flatten_product_bricks(payload.get("bricks", [])))
    for group in payload.get("rootGroups", []) or []:
        walk_group(group)
    return flat


def collect_capabilities(payload: Any) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []

    def walk_group(group: Any) -> None:
        if not isinstance(group, dict):
            return
        for capability in group.get("capabilities", []) or []:
            if isinstance(capability, dict):
                flat.append(capability)
        for subgroup in group.get("subGroups", []) or []:
            walk_group(subgroup)

    if not isinstance(payload, dict):
        return flat

    # Support both legacy flat schemas and the current rootGroups/subGroups structure.
    for capability in payload.get("capabilities", []) or []:
        if isinstance(capability, dict):
            flat.append(capability)
    for group in payload.get("rootGroups", []) or []:
        walk_group(group)
    return flat


def call_gemini_nanobanana_api(api_key: str, prompt: str, model: str) -> bytes:
    request_url = API_URL_TEMPLATE.format(
        model=urllib.parse.quote(model, safe=""),
        api_key=urllib.parse.quote(api_key, safe=""),
    )
    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": "1:1",
                    "imageSize": "1K",
                },
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        request_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while calling Gemini Nano Banana API: {exc}") from exc

    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(f"Unexpected Gemini response: {payload}")

    text_parts: list[str] = []

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
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
            inline_data = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline_data, dict):
                continue
            mime_type = str(inline_data.get("mimeType") or inline_data.get("mime_type") or "").lower()
            if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
                continue
            data = inline_data.get("data")
            if isinstance(data, str):
                return base64.b64decode(data)

    extra = f" Text parts: {' | '.join(text_parts)}" if text_parts else ""
    raise RuntimeError(f"Gemini response did not contain inline image data.{extra} Payload: {payload}")


def build_kpi_prompt(
    domain_name: str,
    domain_description: str,
    customer: dict[str, Any],
    kpi: dict[str, Any],
    kpi_scope: str,
) -> str:
    return f"""
Create a square KPI icon for a product-strategy dashboard.

KPI: {kpi.get("name", "")}
KPI description: {kpi.get("description", "")}

Icon requirements:
- A minimalist icon in a clean, professional line-art style, no text.
- No text, or labels.
- No borders or frames.
- The design features bold, consistent black outlines with rounded stroke ends.
- Use thick, uniform line weights and simple geometric shapes.
- No shading, no gradients, and no colors, only high-contrast black and white vector-style graphics.
""".strip()


def build_start_logo_prompt(domain_name: str, domain_description: str) -> str:
    return f"""
Create a square domain logo icon for an internal product architecture start page.

Domain: {domain_name}

Logo requirements:
- A minimalist icon in a clean, professional line-art style, no text.
- No text, or labels.
- No borders or frames.
- The design features bold, consistent black outlines with rounded stroke ends.
- Use thick, uniform line weights and simple geometric shapes.
- No shading, no gradients, and no colors—only high-contrast black and white vector-style graphics.

""".strip()


def build_brick_prompt(domain_name: str, domain_description: str, brick: dict[str, Any]) -> str:
    return f"""
Create a square technical capability icon.

Capability: {brick.get("name", "")}

Icon requirements:
- A minimalist icon in a clean, professional line-art style, no text.
- No text, or labels.
- Without borders and without frames.
- The design features bold, consistent black outlines.
- Use thick, uniform line weights and simple geometric shapes.
- No shading, no gradients, and no colors—only high-contrast black and white vector-style graphics.
""".strip()


def build_capability_prompt(domain_name: str, domain_description: str, capability: dict[str, Any]) -> str:
    return f"""
Create a square product experience icon.

Product capability: {capability.get("name", "")}
Description: {capability.get("description", "")}

Icon requirements:
- A minimalist icon in a clean, professional line-art style, no text.
- No text, or labels.
- Without borders and without frames.
- The design features bold, consistent black outlines.
- Use thick, uniform line weights and simple geometric shapes.
- No shading, no gradients, and no colors—only high-contrast black and white vector-style graphics.
""".strip()


def iter_kpi_nodes(customer: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []

    def walk(node: Any, scope: str) -> None:
        if not isinstance(node, dict):
            return
        if node.get("name"):
            nodes.append((scope, node))
        for child in node.get("children", []) or []:
            walk(child, scope)

    pyramids = customer.get("kpiPyramids") or {}
    customer_outcomes = pyramids.get("customerOutcomes") or {}
    business_outcomes = pyramids.get("businessOutcomes") or {}

    walk(customer_outcomes.get("top"), "customer-outcomes")
    for branch in customer_outcomes.get("branches", []) or []:
        walk(branch, "customer-outcomes")

    walk(business_outcomes.get("top"), "business-outcomes")
    for branch in business_outcomes.get("branches", []) or []:
        walk(branch, "business-outcomes")

    return nodes


def should_generate(path: Path, args: argparse.Namespace, generated_count: int) -> bool:
    if args.json_only:
        return False
    if args.limit and generated_count >= args.limit:
        return False
    if args.skip_existing and path.exists():
        return False
    if path.exists() and not args.overwrite and not args.skip_existing:
        return False
    return True


def generate_icon(
    *,
    api_key: str,
    prompt: str,
    path: Path,
    args: argparse.Namespace,
    generated_count: int,
) -> bool:
    if not should_generate(path, args, generated_count):
        print(f"Skipping icon: {path}")
        return False

    ensure_dir(path.parent, args.dry_run)
    print(f"Generating icon: {path}")
    if not args.dry_run:
        image_bytes = call_gemini_nanobanana_api(api_key, prompt, args.model)
        print(f"Postprocessing icon: {path}")
        image_bytes = postprocess_icon_bytes(image_bytes)
        write_image(path, image_bytes, dry_run=False)
    else:
        write_image(path, b"", dry_run=True)
    if args.sleep_seconds > 0 and not args.dry_run:
        time.sleep(args.sleep_seconds)
    return True


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not args.json_only and not args.dry_run and not api_key:
        print(f"{args.api_key_env} is required unless --json-only or --dry-run is used.")
        return 2

    domains = list_domains(args.domain)
    if not domains:
        print("No product domains found for the selected scope.")
        return 1

    total_generated = 0
    total_json_updates = 0
    processed_icon_paths: set[Path] = set()

    for domain_dir in domains:
        start_config_path = domain_dir / "start" / "config.json"
        domain_name = domain_dir.name
        domain_description = ""
        if start_config_path.exists():
            start_config = load_json(start_config_path)
            domain_name = str(start_config.get("name") or domain_name)
            domain_description = str(start_config.get("description") or "")

        if start_config_path.exists():
            start_logo_path = domain_dir / "start" / "icons" / "logo.png"
            if start_logo_path not in processed_icon_paths:
                processed_icon_paths.add(start_logo_path)
                if generate_icon(
                    api_key=api_key,
                    prompt=build_start_logo_prompt(domain_name, domain_description),
                    path=start_logo_path,
                    args=args,
                    generated_count=total_generated,
                ):
                    total_generated += 1

        customers_json_path = domain_dir / "customers" / "customers.json"
        if customers_json_path.exists():
            customer_json_changed = False
            if not args.skip_customer_icons:
                generated, customer_json_changed = generate_icons_for_file(
                    customers_json_path, args, api_key, total_generated
                )
                total_generated += generated
            # Reload after the portrait generator saves customer icon references.
            payload = load_json(customers_json_path)
            original_text = json.dumps(payload, indent=2, ensure_ascii=False)
            json_changed = False
            if isinstance(payload, list):
                for group in payload:
                    if not isinstance(group, dict):
                        continue
                    for customer in group.get("customers", []) or []:
                        if not isinstance(customer, dict):
                            continue
                        customer_id = str(customer.get("id") or "customer")
                        for kpi_scope, kpi_node in iter_kpi_nodes(customer):
                            kpi_id = str(kpi_node.get("id") or slugify(str(kpi_node.get("name") or "kpi")))
                            filename = normalize_icon_filename(
                                kpi_node.get("icon"),
                                f"kpi-{customer_id}-{kpi_id}",
                            )
                            if kpi_node.get("icon") != filename:
                                kpi_node["icon"] = filename
                                json_changed = True
                            icon_path = customers_json_path.parent / "icons" / filename
                            if icon_path in processed_icon_paths:
                                continue
                            processed_icon_paths.add(icon_path)
                            prompt = build_kpi_prompt(
                                domain_name,
                                domain_description,
                                customer,
                                kpi_node,
                                kpi_scope,
                            )
                            if generate_icon(
                                api_key=api_key,
                                prompt=prompt,
                                path=icon_path,
                                args=args,
                                generated_count=total_generated,
                            ):
                                total_generated += 1
            updated_text = json.dumps(payload, indent=2, ensure_ascii=False)
            if json_changed or updated_text != original_text:
                dump_json(customers_json_path, payload, args.dry_run)
                customer_json_changed = True
            total_json_updates += int(customer_json_changed)

        product_bricks_path = domain_dir / "product-bricks" / "product-bricks.json"
        if product_bricks_path.exists():
            bricks_payload = load_json(product_bricks_path)
            bricks = collect_bricks(bricks_payload)

            for brick in bricks:
                brick_id = str(brick.get("id") or "").strip()
                if not brick_id:
                    continue
                icon_path = domain_dir / "product-bricks" / "icons" / f"{brick_id}.png"
                if icon_path in processed_icon_paths:
                    continue
                processed_icon_paths.add(icon_path)
                if generate_icon(
                    api_key=api_key,
                    prompt=build_brick_prompt(domain_name, domain_description, brick),
                    path=icon_path,
                    args=args,
                    generated_count=total_generated,
                ):
                    total_generated += 1

        product_capabilities_path = domain_dir / "product-bricks" / "product-capability.json"
        if product_capabilities_path.exists():
            capabilities_payload = load_json(product_capabilities_path)
            original_text = json.dumps(capabilities_payload, indent=2, ensure_ascii=False)
            json_changed = False
            capabilities = collect_capabilities(capabilities_payload)

            for capability in capabilities:
                if not isinstance(capability, dict):
                    continue
                capability_id = str(capability.get("id") or "").strip()
                if not capability_id:
                    continue

                filename = normalize_icon_filename(capability.get("icon"), capability_id)
                if capability.get("icon") != filename:
                    capability["icon"] = filename
                    json_changed = True

                icon_path = domain_dir / "product-bricks" / "icons" / filename
                if icon_path in processed_icon_paths:
                    continue
                processed_icon_paths.add(icon_path)
                if generate_icon(
                    api_key=api_key,
                    prompt=build_capability_prompt(domain_name, domain_description, capability),
                    path=icon_path,
                    args=args,
                    generated_count=total_generated,
                ):
                    total_generated += 1

            updated_text = json.dumps(capabilities_payload, indent=2, ensure_ascii=False)
            if json_changed or updated_text != original_text:
                dump_json(product_capabilities_path, capabilities_payload, args.dry_run)
                total_json_updates += 1

    print(
        f"Completed. Generated {total_generated} icons and updated {total_json_updates} JSON files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

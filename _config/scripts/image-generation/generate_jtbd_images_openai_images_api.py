#!/usr/bin/env python3
# Generate JTBD images via the OpenAI Images API.

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request

from jtbd_image_generation_common import GeneratedImage, GenerationTarget, build_argument_parser, run_generation

DEFAULT_MODEL = "gpt-image-1.5"
DEFAULT_QUALITY = "low"
API_URL = "https://api.openai.com/v1/images/generations"


def parse_args() -> argparse.Namespace:
    return build_argument_parser(
        description="Generate JTBD images using the OpenAI Images API.",
        default_model=DEFAULT_MODEL,
        default_quality=DEFAULT_QUALITY,
        output_formats=("png",),
    ).parse_args()


def call_openai_images_api(
        api_key: str,
        target: GenerationTarget,
        args: argparse.Namespace,
) -> GeneratedImage:
    body = json.dumps(
        {
            "model": args.model,
            "prompt": target.prompt,
            "quality": args.quality,
            "background": args.background,
            "output_format": "png",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while calling OpenAI Images API: {exc}") from exc

    data = payload.get("data") or []
    if not data:
        raise RuntimeError(f"Unexpected OpenAI Images API response: {payload}")

    image_b64 = data[0].get("b64_json")
    if image_b64:
        return GeneratedImage(image_bytes=base64.b64decode(image_b64), output_format="png")

    image_url = data[0].get("url")
    if image_url:
        with urllib.request.urlopen(image_url, timeout=300) as response:
            return GeneratedImage(image_bytes=response.read(), output_format="png")

    raise RuntimeError(f"OpenAI Images API response did not contain image data: {payload}")


def main() -> int:
    args = parse_args()
    args.output_format = "png"
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    return run_generation(
        args=args,
        api_key=api_key,
        api_key_label="OPENAI_API_KEY",
        generate_image=call_openai_images_api,
    )


if __name__ == "__main__":
    raise SystemExit(main())

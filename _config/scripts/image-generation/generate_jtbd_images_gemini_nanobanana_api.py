#!/usr/bin/env python3
# Generate JTBD images via the Gemini Nano Banana image API.

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from jtbd_image_generation_common import GeneratedImage, GenerationTarget, build_argument_parser, run_generation

DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_QUALITY = "low"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
)
MIME_TYPE_TO_FORMAT = {
    "image/png": "png"
}
OUTPUT_FORMAT="png"

def parse_args() -> argparse.Namespace:
    parser = build_argument_parser(
        description="Generate JTBD images using the Gemini Nano Banana image API.",
        default_model=DEFAULT_MODEL,
        default_quality=DEFAULT_QUALITY,
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
            return GeneratedImage(image_bytes=base64.b64decode(data), output_format=OUTPUT_FORMAT)

    raise RuntimeError(f"Gemini response did not contain inline image data: {payload}")


def call_gemini_nanobanana_api(
        api_key: str,
        target: GenerationTarget,
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


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    return run_generation(
        args=args,
        api_key=api_key,
        api_key_label=args.api_key_env,
        generate_image=call_gemini_nanobanana_api,
    )


if __name__ == "__main__":
    raise SystemExit(main())

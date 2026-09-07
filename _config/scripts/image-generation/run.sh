#!/bin/bash

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <domain> [--lightweight]" >&2
    exit 2
fi

domain="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lightweight_args=()

if [[ "${2:-}" == "--lightweight" ]]; then
    lightweight_args+=("--lightweight")
elif [[ -n "${2:-}" ]]; then
    echo "Usage: $0 <domain> [--lightweight]" >&2
    exit 2
fi

if [[ -n "${3:-}" ]]; then
    echo "Usage: $0 <domain> [--lightweight]" >&2
    exit 2
fi

python3 "$script_dir/generate_customer_icons_gemini_nanobanana_api.py" --domain "$domain"
python3 "$script_dir/generate_jtbd_images_gemini_nanobanana_api.py" --domain "$domain" "${lightweight_args[@]}"
python3 "$script_dir/generate_journey_images_gemini_nanobanana_api.py" --domain "$domain" "${lightweight_args[@]}"
python3 "$script_dir/generate_customer_relations_images_gemini_nanobanana_api.py" --domain "$domain"
python3 "$script_dir/generate_residuality_images_gemini_nanobanana_api.py" --domain "$domain"

if [[ "${2:-}" != "--lightweight" ]]; then
  python3 "$script_dir/generate_missing_domain_icons_gemini_nanobanana_api.py" --domain "$domain" --skip-customer-icons
fi

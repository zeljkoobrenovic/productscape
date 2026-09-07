#!/bin/bash

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <domain-folder> [--lightweight]" >&2
    exit 2
fi

domain_dir="$1"
script_dir="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
lightweight_args=()

if [[ "${2:-}" == "--lightweight" ]]; then
    lightweight_args+=("--lightweight")
elif [[ -n "${2:-}" ]]; then
    echo "Usage: $0 <domain-folder> [--lightweight]" >&2
    exit 2
fi

if [[ -n "${3:-}" ]]; then
    echo "Usage: $0 <domain-folder> [--lightweight]" >&2
    exit 2
fi

if [[ ! -d "$domain_dir" ]]; then
    echo "Domain folder does not exist: $domain_dir" >&2
    exit 2
fi

domain_dir="$(CDPATH= cd -- "$domain_dir" && pwd -P)" || exit 2
domains_dir="$(dirname "$(dirname "$domain_dir")")"
if [[ "$domains_dir" != */_config/product-domains ]]; then
    echo "Expected a domain folder at <project>/_config/product-domains/<group>/<domain-id>: $domain_dir" >&2
    exit 2
fi

# The folder selects the data project; Python generators still take its domain ID.
export PRODUCTSCAPES_PROJECT="$(dirname "$(dirname "$domains_dir")")"
domain="${domain_dir##*/}"

python3 "$script_dir/generate_customer_icons_gemini_nanobanana_api.py" --domain "$domain"
python3 "$script_dir/generate_jtbd_images_gemini_nanobanana_api.py" --domain "$domain" "${lightweight_args[@]}"
python3 "$script_dir/generate_journey_images_gemini_nanobanana_api.py" --domain "$domain" "${lightweight_args[@]}"
python3 "$script_dir/generate_customer_relations_images_gemini_nanobanana_api.py" --domain "$domain"
python3 "$script_dir/generate_residuality_images_gemini_nanobanana_api.py" --domain "$domain"

if [[ "${2:-}" != "--lightweight" ]]; then
  python3 "$script_dir/generate_missing_domain_icons_gemini_nanobanana_api.py" --domain "$domain" --skip-customer-icons
fi

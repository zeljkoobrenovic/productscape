import sys


def load_domain_args():
    if len(sys.argv) != 4:
        raise SystemExit(
            f"Usage: python3 {sys.argv[0]} <domain_id> <domain_name> <domain_description>"
        )

    domain = {
        "id": sys.argv[1],
        "name": sys.argv[2],
        "description": sys.argv[3],
    }
    site_config = {"domains": [domain]}
    return domain, site_config

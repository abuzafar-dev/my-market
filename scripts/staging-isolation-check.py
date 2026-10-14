"""Check that a resolved staging Compose config cannot collide with production.

Usage (docs/STAGING.md §0a):

    scripts/staging-compose.sh config --format json | python3 scripts/staging-isolation-check.py

Reads the resolved config on stdin and prints only names, ports, aliases,
ALLOWED_HOSTS and whether the WhatsApp token is set — never a secret value.
Exit status 0 = isolated, 1 = a collision with production's resources.
"""

import json
import sys

PROJECT = "my-market-staging"
PRODUCTION = {"project": "my-market", "port": "8080", "alias": "my-market"}


def main() -> int:
    config = json.load(sys.stdin)
    problems = []

    print(f"project         {config['name']}")
    if config["name"] != PROJECT:
        problems.append(f"project name is {config['name']!r}, expected {PROJECT!r}")

    for name, service in sorted(config["services"].items()):
        if service.get("container_name"):
            problems.append(f"{name}: fixed container_name {service['container_name']!r}")
        for port in service.get("ports", []):
            published = str(port.get("published"))
            print(f"host port       {port.get('host_ip') or '0.0.0.0'}:{published} -> {name}")
            if published == PRODUCTION["port"]:
                problems.append(f"{name}: host port {published} is production's")
        for network in (service.get("networks") or {}).values():
            for alias in (network or {}).get("aliases") or []:
                print(f"proxy alias     {alias} ({name})")
                if alias == PRODUCTION["alias"]:
                    problems.append(f"{name}: proxy alias {alias!r} is production's")
        env = service.get("environment") or {}
        if "SECRET_KEY" in env:  # an app container (backend / celery / beat)
            token = "set" if env.get("WHATSAPP_ACCESS_TOKEN") else "EMPTY"
            print(
                f"app env         {name}: ALLOWED_HOSTS={env.get('ALLOWED_HOSTS', '')} "
                f"WHATSAPP_ACCESS_TOKEN={token}"
            )

    for volume in sorted(v["name"] for v in config.get("volumes", {}).values()):
        print(f"volume          {volume}")
        if not volume.startswith(f"{PROJECT}_"):
            problems.append(f"volume {volume!r} is not staging-prefixed")

    for network in config.get("networks", {}).values():
        if network.get("external"):
            print(f"network         {network['name']} (external — shared on purpose)")
        else:
            print(f"network         {network['name']}")
            if not network["name"].startswith(f"{PROJECT}_"):
                problems.append(f"network {network['name']!r} is not staging-prefixed")

    hosts = {
        (service.get("environment") or {}).get("ALLOWED_HOSTS")
        for service in config["services"].values()
        if "SECRET_KEY" in (service.get("environment") or {})
    }
    if len(hosts) > 1:
        problems.append("app containers disagree on ALLOWED_HOSTS (mixed env files)")

    if problems:
        print("RESULT          COLLISION")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("RESULT          ISOLATED (check ALLOWED_HOSTS above is the staging domain)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

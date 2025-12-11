# src/main.py

import argparse
from .travsport_api import (
    build_client,
    resolve_horse,
    fetch_pedigree_html,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Horse name to lookup")
    parser.add_argument("--year", required=False, type=int, help="Birth year")
    args = parser.parse_args()

    name = args.name
    year = args.year

    print(f"[main] Looking up horse: '{name}' year={year} on travsport.se")

    # Build HTTP client
    session = build_client()

    # Resolve horse identity (stub for now)
    horse = resolve_horse(session, name, year)
    print(f"[main] Resolved horse: {horse}")

    # Fetch pedigree HTML (stub)
    html = fetch_pedigree_html(session, horse)
    print(f"[main] Received pedigree HTML (length={len(html)})")

    print("\n[main] Pipeline completed (stub mode).")


if __name__ == "__main__":
    main()
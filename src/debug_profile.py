# src/debug_profile.py
from __future__ import annotations

import json
import re
import argparse
from .travsport_api import build_client
from .horse_profile_api import fetch_horse_profile_html


def find_all_json_blocks(html: str):
    """
    Find ALL Next.js JSON hydration blocks and print them.
    This helps reverse-engineer which one contains birthYear.
    """
    results = []

    # Pattern that captures all `"data":{"data":{ ... }}`
    pattern = r'"data":\{"data":\{'
    for match in re.finditer(pattern, html):
        start = match.start()

        # Walk forward to matching brace
        depth = 0
        obj_start = html.find("{", start)
        if obj_start == -1:
            continue

        for i in range(obj_start, len(html)):
            ch = html[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj_end = i + 1
                    raw = html[obj_start:obj_end]
                    try:
                        clean = raw.replace(r"\"", '"')
                        data = json.loads(clean)
                        results.append(data)
                    except Exception:
                        pass
                    break

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horse-id", required=True, type=int)
    args = parser.parse_args()

    session = build_client()
    html = fetch_horse_profile_html(session, args.horse_id)

    blocks = find_all_json_blocks(html)

    print(f"Found {len(blocks)} JSON blocks.\n")

    for i, block in enumerate(blocks):
        print("=" * 80)
        print(f"BLOCK {i}")
        print(json.dumps(block, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
# src/birthyear_utils.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
import time

from .horse_profile_api import get_birth_year


def enrich_birth_years(
    flat_nodes: List[Dict[str, Any]],
    session,
    delay_seconds: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    Enrich each flattened pedigree node with a birth_year field.

    - Uses horse_profile_api.get_birth_year(session, horse_id).
    - Caches results per horse_id so we never query the same ID twice.
    - Optional delay between requests to be polite to the server.

    Mutates the node dicts in-place and also returns the list for convenience.
    """
    cache: Dict[int, Optional[int]] = {}

    for node in flat_nodes:
        hid = node.get("horse_id")

        # No ID → no lookup
        if hid is None:
            node["birth_year"] = None
            continue

        # Reuse cached result if we've seen this horse before
        if hid in cache:
            node["birth_year"] = cache[hid]
            continue

        # New horse_id → fetch birth year
        year = get_birth_year(session, hid)
        cache[hid] = year
        node["birth_year"] = year

        # Be polite: small pause between HTTP requests
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return flat_nodes
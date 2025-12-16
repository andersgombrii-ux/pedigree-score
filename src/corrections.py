# src/corrections.py

from __future__ import annotations
from typing import List, Dict, Any


def apply_manual_corrections(flat_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply manual / curated corrections to the flattened lineage list.
    """

    for node in flat_list:
        name = (node.get("name") or "").upper()
        birth_year = node.get("birth_year")
        horse_id = node.get("horse_id")

        # Kaprell mis-id fix:
        # - travsport.se has KAPRELL (NO) 1912 with horse_id 81414
        # - correct horse is Kaprell 1955 (from travsport.no)
        if name.startswith("KAPRELL") and birth_year == 1912 and horse_id == 81414:
            # Detach from wrong travsport.se identity
            node["horse_id"] = None

            # Correct birth year
            node["birth_year"] = 1955

            # Optional provenance / status flags
            node["birth_year_source"] = "override_travsport_no"
            node["parentage_status"] = "unknown"
            node["identity_status"] = "misidentified_fixed"

            # Parents from the wrong Kaprell should not be trusted
            node["father_id"] = None
            node["mother_id"] = None

    return flat_list
# src/corrections.py

from __future__ import annotations
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Canonical historical identities
# ---------------------------------------------------------------------------

# Internal canonical ID for Kaprell (NO)
# Negative to avoid collision with Travsport numeric IDs
KAPRELL_ID = -275
KAPRELL_REGNO = "T-275"


def apply_manual_corrections(flat_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply manual / curated corrections to the flattened lineage list.

    This function is intentionally deterministic and conservative:
    - No fuzzy name merging
    - No global heuristics
    - Only explicit, evidence-backed rewrites

    Current rules:
    1) Canonicalize Kaprell (NO) using registration number T-275
    2) Repair all parent edges that explicitly reference Kaprell as sire
    3) Preserve provenance flags for known misidentifications
    """

    for node in flat_list:
        name = (node.get("name") or "").upper()
        birth_year = node.get("birth_year")
        horse_id = node.get("horse_id")
        regno = node.get("registration_number")

        # -------------------------------------------------------------------
        # Rule 1: Canonicalize Kaprell's own node
        # -------------------------------------------------------------------
        if regno == KAPRELL_REGNO:
            # Assign canonical internal ID
            node["horse_id"] = KAPRELL_ID

            # Ensure correct historical metadata
            if birth_year != 1955:
                node["birth_year"] = 1955
                node["birth_year_source"] = "override_travsport_no"

            node.setdefault("parentage_status", "unknown")
            node.setdefault("identity_status", "manual_registry")

            # Kaprell's own parents are historically unreliable in upstream data
            node["father_id"] = None
            node["mother_id"] = None

        # -------------------------------------------------------------------
        # Rule 2: Repair misidentified Kaprell edge from travsport.se (legacy)
        # -------------------------------------------------------------------
        # travsport.se historically exposes a wrong Kaprell:
        #   - birth year ~1912
        #   - horse_id 81414
        # We detach that identity and let Rule 1 re-bind via regno.
        if (
            name.startswith("KAPRELL")
            and birth_year == 1912
            and horse_id == 81414
        ):
            node["horse_id"] = KAPRELL_ID
            node["birth_year"] = 1955
            node["birth_year_source"] = "override_travsport_no"
            node["parentage_status"] = "unknown"
            node["identity_status"] = "misidentified_fixed"
            node["father_id"] = None
            node["mother_id"] = None

        # -------------------------------------------------------------------
        # Rule 3: Canonicalize parent edges pointing to Kaprell
        # -------------------------------------------------------------------
        # This is the scalable fix: every descendant of Kaprell is repaired
        # automatically based on explicit parent registration number.
        if node.get("father_registration_number") == KAPRELL_REGNO:
            node["father_id"] = KAPRELL_ID

        if node.get("mother_registration_number") == KAPRELL_REGNO:
            node["mother_id"] = KAPRELL_ID

    return flat_list
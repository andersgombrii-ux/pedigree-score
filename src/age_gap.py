# src/age_gap.py

from __future__ import annotations
from typing import List, Dict, Any, Optional


def build_index(flat_list: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Returns a dictionary: horse_id -> node
    Skips nodes with null horse_id.
    """
    return {
        node["horse_id"]: node
        for node in flat_list
        if node.get("horse_id") is not None
    }


def compute_gap(child_year: Optional[int], parent_year: Optional[int]) -> Optional[int]:
    """
    Computes age gap. Returns None if missing.
    """
    if not child_year or not parent_year:
        return None
    return child_year - parent_year


def classify_gap(gap: Optional[int]) -> str:
    """
    Categorize age gap for quality checks.
    """
    if gap is None:
        return "unknown"
    if gap < 2:
        return "impossible"
    if gap < 8:
        return "very_unusual"
    if gap > 30:
        return "suspicious"
    return "normal"


def compute_age_gaps(flat_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compute sire and dam age gaps for each node in the flattened pedigree.

    Output format example:

    {
        "child_name": "Moe Odin",
        "child_id": 501290,
        "parent_type": "father",
        "parent_name": "Elding",
        "parent_id": 42462,
        "child_birth_year": 1997,
        "parent_birth_year": 1983,
        "gap": 14,
        "classification": "normal"
    }
    """
    index = build_index(flat_list)
    results = []

    for node in flat_list:
        child_id = node.get("horse_id")
        child_year = node.get("birth_year")
        child_name = node.get("name")

        for parent_type in ("father", "mother"):
            parent_id = node.get(f"{parent_type}_id")

            if parent_id and parent_id in index:
                parent = index[parent_id]
                parent_name = parent.get("name")
                parent_year = parent.get("birth_year")

            else:
                parent = None
                parent_name = None
                parent_year = None

            gap = compute_gap(child_year, parent_year)
            classification = classify_gap(gap)

            results.append({
                "child_name": child_name,
                "child_id": child_id,
                "parent_type": parent_type,
                "parent_name": parent_name,
                "parent_id": parent_id,
                "child_birth_year": child_year,
                "parent_birth_year": parent_year,
                "gap": gap,
                "classification": classification,
            })

    return results
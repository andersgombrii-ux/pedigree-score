from __future__ import annotations

import hashlib
import json
from typing import Dict, Any, Tuple

from .pedigree_store import DEFAULT_CACHE_DIR
from .pedigree_graph_store import load_merged_graph, save_merged_graph


PedigreeNode = dict
PedigreeGraph = Dict[int, PedigreeNode]

# ---------------------------------------------------------------------------
# Curated canonical identities (must match corrections.py intent)
# ---------------------------------------------------------------------------

# Kaprell (NO): canonical internal ID + regno
KAPRELL_ID = -275
KAPRELL_REGNO = "T-275"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_all_cached_pedigrees() -> list[list[dict]]:
    """
    Load all cached flattened pedigrees from DEFAULT_CACHE_DIR.

    Supports:
      - legacy cache files where the JSON root is a list[dict]
      - versioned cache files (v2+) where JSON root is a dict containing "horses": list[dict]
        e.g. {"cache_version": 2, ..., "horses": [...]}

    Returns: list of flat pedigree lists.
    """
    pedigrees: list[list[dict]] = []

    if not DEFAULT_CACHE_DIR.exists():
        return pedigrees

    for path in DEFAULT_CACHE_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Legacy: top-level list
            if isinstance(data, list):
                pedigrees.append(data)
                continue

            # Versioned: top-level dict with "horses"
            if isinstance(data, dict):
                horses = data.get("horses")
                if isinstance(horses, list):
                    pedigrees.append(horses)
                    continue

        except Exception:
            continue

    return pedigrees


def _synthetic_id(token: str) -> int:
    """
    Deterministically map a non-numeric identifier (e.g. 'T-275') to a stable negative int.
    """
    s = token.strip()
    h = hashlib.md5(s.encode("utf-8")).hexdigest()[:16]  # 64 bits of hex
    n = int(h, 16)
    return -int(n % 2_000_000_000 + 1)


def _canon_id(v: Any) -> Tuple[int | None, str | None]:
    """
    Canonicalize an identifier into an int key for the merged graph.

    Returns:
      (canonical_int_id | None, external_id_str | None)

    Rules:
      - int -> (int, None)
      - digit-string -> (int, None)
      - curated non-numeric tokens (e.g. Kaprell regno 'T-275') -> (curated int, original string)
      - non-empty non-digit string -> (stable negative int, original string)
      - otherwise -> (None, None)
    """
    if isinstance(v, int):
        return v, None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None, None
        if s.isdigit():
            return int(s), None

        if s.upper() == KAPRELL_REGNO:
            return KAPRELL_ID, s

        return _synthetic_id(s), s
    return None, None


def _node_id_source(node: dict) -> Any:
    """
    Select the best available identifier for a node.

    Priority:
      1) horse_id (Travsport numeric when available)
      2) registration_number (e.g. 'T-275' for legacy horses)
    """
    hid = node.get("horse_id")
    if hid is not None:
        return hid
    reg = node.get("registration_number")
    if isinstance(reg, str) and reg.strip():
        return reg.strip()
    return None


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in ("", "unknown", "none", "null", "?"):
        return True
    return False


def _is_curated_negative_id(v: Any) -> bool:
    """
    True for small negative IDs we treat as curated/canonical
    (as opposed to large negative synthetic hash IDs).
    """
    return isinstance(v, int) and v < 0 and abs(v) <= 1_000_000


def _looks_like_kaprell_context(node: dict) -> bool:
    """
    Best-effort check: does this node explicitly say its sire is Kaprell via regno/name labels?
    """
    fr = node.get("father_registration_number")
    if isinstance(fr, str) and fr.strip().upper() == KAPRELL_REGNO:
        return True
    fn = node.get("father_name")
    if isinstance(fn, str) and fn.strip().upper().startswith("KAPRELL"):
        return True
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_merged_pedigree_graph(
    *,
    force_rebuild: bool = False,
) -> PedigreeGraph:
    """
    Merge all cached pedigrees into a single ancestry graph.

    Guarantees:
      - graph keys are ints (horse_id), including stable synthetic negative ints for non-numeric IDs
      - curated overrides prevent known registry numbers (e.g. Kaprell T-275) from becoming synthetic duplicates
      - father_id/mother_id are ints or None
      - sex is preserved when known

    IMPORTANT:
      - Cache files are versioned now (v2+). We must read `{"horses": [...]}` payloads.
    """

    if not force_rebuild:
        cached = load_merged_graph()
        if cached is not None:
            print(f"[merged-graph] Loaded cached graph ({len(cached)} nodes)")
            return cached

    print("[merged-graph] Building merged pedigree graph from flat caches…")

    graph: PedigreeGraph = {}

    for pedigree in load_all_cached_pedigrees():
        for node in pedigree:
            hid_source = _node_id_source(node)
            hid, hid_external = _canon_id(hid_source)
            if hid is None:
                continue

            father_id, father_external = _canon_id(node.get("father_id"))
            mother_id, mother_external = _canon_id(node.get("mother_id"))
            sex = node.get("sex")

            if hid not in graph:
                merged_node = {
                    **dict(node),
                    "horse_id": hid,
                    "father_id": father_id,
                    "mother_id": mother_id,
                    "sex": sex,
                }

                if hid_external is not None:
                    merged_node["external_id"] = hid_external
                if father_external is not None:
                    merged_node["father_external_id"] = father_external
                if mother_external is not None:
                    merged_node["mother_external_id"] = mother_external

                graph[hid] = merged_node
                continue

            existing = graph[hid]

            # canonical ids consistent
            if existing.get("horse_id") != hid:
                existing["horse_id"] = hid
            if hid_external is not None and _is_missing(existing.get("external_id")):
                existing["external_id"] = hid_external

            # Father merge (with curated overwrite support)
            if father_id is not None:
                if _is_missing(existing.get("father_id")):
                    existing["father_id"] = father_id
                else:
                    if (
                        isinstance(existing.get("father_id"), int)
                        and existing.get("father_id") != father_id
                        and (
                            father_id == KAPRELL_ID
                            or _looks_like_kaprell_context(node)
                            or _is_curated_negative_id(father_id)
                        )
                    ):
                        existing["father_id"] = father_id

            # Mother merge (curated overwrite support)
            if mother_id is not None:
                if _is_missing(existing.get("mother_id")):
                    existing["mother_id"] = mother_id
                else:
                    if (
                        isinstance(existing.get("mother_id"), int)
                        and existing.get("mother_id") != mother_id
                        and _is_curated_negative_id(mother_id)
                    ):
                        existing["mother_id"] = mother_id

            if father_external is not None and _is_missing(existing.get("father_external_id")):
                existing["father_external_id"] = father_external
            if mother_external is not None and _is_missing(existing.get("mother_external_id")):
                existing["mother_external_id"] = mother_external

            # merge sex
            if _is_missing(existing.get("sex")) and not _is_missing(sex):
                existing["sex"] = sex

            # merge birth_year
            if _is_missing(existing.get("birth_year")) and not _is_missing(node.get("birth_year")):
                existing["birth_year"] = node.get("birth_year")

            # merge name
            if _is_missing(existing.get("name")) and not _is_missing(node.get("name")):
                existing["name"] = node.get("name")

            # merge registration_number
            if _is_missing(existing.get("registration_number")) and not _is_missing(node.get("registration_number")):
                existing["registration_number"] = node.get("registration_number")

    save_merged_graph(graph)
    print(f"[merged-graph] Saved merged graph ({len(graph)} nodes)")

    return graph

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import re


@dataclass
class PedigreeNode:
    """One horse/person in the pedigree."""
    name: str
    generation: int  # 0 = focus horse, 1 = parents, etc.
    horse_id: Optional[int] = None
    registration_number: Optional[str] = None
    record: Optional[str] = None
    father: Optional["PedigreeNode"] = None
    mother: Optional["PedigreeNode"] = None

    # NEW: preserves role in the tree so downstream flattening can reliably
    # identify which node is the father/mother at every level, even when
    # upstream numeric IDs are wrong/missing.
    parent_role: Optional[str] = None  # "father" | "mother" | None


@dataclass
class PedigreeTree:
    """Rooted pedigree tree with convenience helpers."""
    root: PedigreeNode
    nodes: List[PedigreeNode]

    @property
    def root_name(self) -> str:
        return self.root.name

    @property
    def max_generations(self) -> int:
        return max(n.generation for n in self.nodes)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_lineage_json_from_html(html: str) -> Dict[str, Any]:
    """
    Extract the root lineage JSON object from the Travsport printpedigree HTML.

    The relevant block is part of the 'lineage-large-<horseId>' query and
    appears inside a JavaScript string with escaped quotes, e.g.:

        \"lineage-large-501290\"
        \"data\":{\"data\":{ ... }}

    We:
      1) Find the escaped '\"lineage-large-...' marker.
      2) From that position, search *backwards* for the escaped \"data\":{\"data\":{.
      3) Starting from the '{', walk by brace depth until the matching '}'.
      4) Unescape quotes (\" -> ") and json.loads() the result.
    """
    # 1) find the lineage query marker (escaped)
    lineage_marker = '\\"lineage-large-'
    marker_index = html.find(lineage_marker)
    if marker_index == -1:
        raise ValueError(
            "Could not find '\\\"lineage-large-*' pedigree data in HTML. "
            "The Travsport page format may have changed."
        )

    # 2) find the escaped \"data\":{\"data\":{ block *before* that marker
    data_block_pattern = '\\"data\\":{\\"data\\":{'
    data_index = html.rfind(data_block_pattern, 0, marker_index)
    if data_index == -1:
        raise ValueError(
            "Could not locate pedigree JSON '\\\"data\\\\\":{\\\"data\\\\\":{' "
            "block before the 'lineage-large-*' marker."
        )

    # index of the opening '{' for the JSON object
    obj_start = data_index + len(data_block_pattern) - 1
    if obj_start >= len(html) or html[obj_start] != "{":
        raise ValueError(
            "Internal parser error: expected '{' at start of pedigree JSON."
        )

    # 3) brace-matching scan to find end of the JSON object
    depth = 0
    end_index: Optional[int] = None
    for i in range(obj_start, len(html)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_index = i + 1  # slice end is exclusive
                break

    if end_index is None:
        raise ValueError("Could not find end of pedigree JSON object in HTML.")

    raw_json_fragment = html[obj_start:end_index]

    # 4) unescape quotes and parse as JSON
    json_text = raw_json_fragment.replace('\\"', '"')

    try:
        root_obj = json.loads(json_text)
    except json.JSONDecodeError as e:
        snippet = json_text[:200].replace("\n", " ")
        raise ValueError(
            f"Failed to decode pedigree JSON from HTML: {e}. "
            f"Snippet: {snippet!r}"
        ) from e

    return root_obj


def _to_int_or_none(value: Any) -> Optional[int]:
    """
    Best-effort conversion for ids that sometimes appear as strings.
    Returns None if conversion fails or value is empty/None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        try:
            return int(s)
        except ValueError:
            return None
    # occasionally upstream might give floats; don't crash
    try:
        return int(value)
    except Exception:
        return None


# Accept many "hyphen-like" unicode separators often seen in scraped text.
_HYPHEN_LIKE = {
    "\u2010",  # hyphen
    "\u2011",  # non-breaking hyphen
    "\u2012",  # figure dash
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u2212",  # minus sign
    "\uFE63",  # small hyphen-minus
    "\uFF0D",  # fullwidth hyphen-minus
}


def _normalize_regno_text(reg_no: str) -> str:
    """
    Normalize registration numbers so pattern matching works even when the
    input contains unicode dashes/hyphens.
    """
    s = reg_no.strip()
    for ch in _HYPHEN_LIKE:
        s = s.replace(ch, "-")
    # also collapse weird spacing around '-'
    s = re.sub(r"\s*-\s*", "-", s)
    return s


# Very tolerant: "T" + any non-digits (or nothing) + digits.
# Examples matched:
#   T-275, T-275, T  -  275, T275, T/275
_T_REGNO_ANYSEP_RE = re.compile(r"^\s*T\D*(\d+)\s*$", re.IGNORECASE)


def _derive_id_from_registration_number(reg_no: Optional[str]) -> Optional[int]:
    """
    Travsport NO data sometimes omits horseId/id for older/legacy ancestors in the
    lineage JSON, but still provides a stable registration number.

    Key case:
      registration_number = "T-275" (or T-275, etc.) -> horse_id should be -275

    We therefore derive a stable negative integer id for "T<sep><num>" when horse_id
    is missing. This prevents duplicate nodes (one with id=-275, one with id=None)
    which otherwise breaks ancestry connectivity and focus counts.
    """
    if not reg_no:
        return None

    s = _normalize_regno_text(str(reg_no))
    m = _T_REGNO_ANYSEP_RE.match(s)
    if not m:
        return None

    try:
        return -int(m.group(1))
    except ValueError:
        return None


def _build_pedigree_tree(root_obj: Dict[str, Any], max_generation: int) -> PedigreeTree:
    """
    Build a complete pedigree tree from lineage JSON.
    Missing ancestors are represented as the same placeholder: "Unknown".

    NOTE:
    We also set `parent_role` on each node ("father"/"mother") based on
    how it is attached in the tree. This is crucial for downstream logic
    that needs to reliably distinguish paternal/maternal lines even when
    upstream numeric IDs are wrong or missing.

    IMPORTANT FIX:
    If Travsport omits numeric IDs but provides registrationNumber (e.g. "T-275"),
    we derive a stable horse_id from registrationNumber to avoid creating duplicate
    disconnected nodes for the same ancestor.
    """
    all_nodes: List[PedigreeNode] = []

    def normalize_name(raw: Optional[str]) -> str:
        if not raw:
            return "Unknown"
        low = raw.strip().lower()
        if low in {"okänd", "okand"} or "uppgift saknas" in low:
            return "Unknown"
        return raw

    def normalize_reg_no(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        return _normalize_regno_text(s)

    def make_unknown_node(generation: int) -> PedigreeNode:
        node = PedigreeNode(
            name="Unknown",
            generation=generation,
            horse_id=None,
            registration_number=None,
            record=None,
            parent_role=None,
        )
        all_nodes.append(node)
        return node

    def build_node(obj: Optional[Dict[str, Any]], generation: int) -> Optional[PedigreeNode]:
        # Stop recursion past max generation depth
        if generation > max_generation:
            return None

        # If parent object is missing → Unknown placeholder
        if obj is None:
            node = make_unknown_node(generation)
        else:
            name = normalize_name(obj.get("name"))

            horse_id_raw = obj.get("horseId") or obj.get("id")
            horse_id = _to_int_or_none(horse_id_raw)

            reg_no = normalize_reg_no(obj.get("registrationNumber"))
            record = obj.get("record")

            # FIX: if numeric id missing but regno present, derive stable id.
            if horse_id is None:
                derived = _derive_id_from_registration_number(reg_no)
                if derived is not None:
                    horse_id = derived

            node = PedigreeNode(
                name=name,
                generation=generation,
                horse_id=horse_id,
                registration_number=reg_no,
                record=record,
                parent_role=None,
            )
            all_nodes.append(node)

        # Expand father & mother unless we reached the last generation
        if generation < max_generation:
            father_obj = obj.get("father") if obj is not None else None
            mother_obj = obj.get("mother") if obj is not None else None

            node.father = build_node(father_obj, generation + 1)
            if node.father is not None:
                node.father.parent_role = "father"

            node.mother = build_node(mother_obj, generation + 1)
            if node.mother is not None:
                node.mother.parent_role = "mother"

        return node

    root_node = build_node(root_obj, generation=0)
    if root_node is None:
        raise ValueError("Pedigree JSON did not contain a valid root horse.")

    # Root has no parent role by definition.
    root_node.parent_role = None

    return PedigreeTree(root=root_node, nodes=all_nodes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pedigree(html: str, max_generation: int = 5) -> PedigreeTree:
    """
    Public entrypoint used by main.py.

    - Extracts the lineage JSON from the HTML.
    - Builds a PedigreeTree up to `max_generation` (0-based; 0 = focus).
      For max_generation = 5:
        total generations (including root) = 6
        expected nodes in a complete tree = 63.
    """
    root_obj = _extract_lineage_json_from_html(html)
    return _build_pedigree_tree(root_obj, max_generation=max_generation)


def supports_six_generations(html: str) -> bool:
    """
    Return True if there is at least one node at generation 5.

    This tells you whether a full 6-generation tree (root + 5 ancestor
    generations) is actually present in the Travsport data for this horse.
    """
    root_obj = _extract_lineage_json_from_html(html)
    tree = _build_pedigree_tree(root_obj, max_generation=5)
    return any(node.generation == 5 for node in tree.nodes)


def node_to_dict(node) -> dict:
    if node is None:
        return None
    return {
        "name": node.name,
        "generation": node.generation,
        "horse_id": node.horse_id,
        "registration_number": node.registration_number,
        "record": node.record,
        "parent_role": node.parent_role,
        "father": node_to_dict(node.father),
        "mother": node_to_dict(node.mother),
    }


def tree_to_dict(tree) -> dict:
    return node_to_dict(tree.root)
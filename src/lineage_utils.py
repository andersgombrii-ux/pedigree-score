from __future__ import annotations

from typing import List, Dict, Any, Optional
from .pedigree_parser import PedigreeTree, PedigreeNode


def _parent_id(node: Optional[PedigreeNode]) -> Any:
    """
    Return the best available identifier for a parent node.

    Priority:
      1. horse_id (int)
      2. registration_number (str)
      3. None
    """
    if node is None:
        return None
    if node.horse_id is not None:
        return node.horse_id
    if node.registration_number:
        return node.registration_number
    return None


def flatten_tree(tree: PedigreeTree) -> List[Dict[str, Any]]:
    """
    Convert a PedigreeTree into a flat list of nodes with generation info.
    Order is guaranteed: generation 0 first, then 1, 2, 3...

    Output format example:
    {
        "name": "MOE ODIN (NO)",
        "generation": 0,
        "horse_id": 501290,
        "registration_number": "NK-970203",
        "record": "23,1ak",
        "parent_role": null,          # "father" | "mother" | null
        "father_id": 42462,           # int OR str (fallback)
        "mother_id": "T-275",         # int OR str (fallback)

        # NEW (labels preserved to enable later canonicalization / corrections):
        "father_name": "KAPRELL (NO)",
        "father_registration_number": "T-275",
        "mother_name": "SÖLVMÖY (NO)",
        "mother_registration_number": "C-20660",
    }

    Notes:
    - The new label fields do not change existing semantics; they only add
      additional context so later stages can deterministically repair
      wrong parent IDs (e.g., Kaprell cases) without manual per-descendant edits.
    """
    flat: List[Dict[str, Any]] = []

    # Breadth-first traversal queue
    queue: List[PedigreeNode] = [tree.root]

    while queue:
        node = queue.pop(0)

        entry: Dict[str, Any] = {
            "name": node.name,
            "generation": node.generation,
            "horse_id": node.horse_id,
            "registration_number": node.registration_number,
            "record": node.record,

            # NEW: preserve the role in the tree (set by parser)
            "parent_role": getattr(node, "parent_role", None),

            # Existing parent id fields (best-effort: int -> regno -> None)
            "father_id": _parent_id(node.father),
            "mother_id": _parent_id(node.mother),

            # NEW: preserve parent labels (for future edge canonicalization)
            "father_name": node.father.name if node.father else None,
            "father_registration_number": node.father.registration_number if node.father else None,
            "mother_name": node.mother.name if node.mother else None,
            "mother_registration_number": node.mother.registration_number if node.mother else None,
        }

        flat.append(entry)

        # push next level
        if node.father:
            queue.append(node.father)
        if node.mother:
            queue.append(node.mother)

    # Sort strictly by generation, stable order inside generations
    flat.sort(key=lambda n: n["generation"])

    return flat
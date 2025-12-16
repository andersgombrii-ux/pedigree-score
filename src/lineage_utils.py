from typing import List, Dict, Any
from .pedigree_parser import PedigreeTree, PedigreeNode


def _parent_id(node: PedigreeNode | None) -> Any:
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
        "father_id": 42462,           # int OR str (fallback)
        "mother_id": "T-275",         # int OR str (fallback)
    }
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
            "father_id": _parent_id(node.father),
            "mother_id": _parent_id(node.mother),
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
from __future__ import annotations

from typing import Dict, Set

PedigreeGraph = Dict[int, dict]


def project_ancestry(
    graph: PedigreeGraph,
    root_id: int,
    max_depth: int = 12,
) -> tuple[PedigreeGraph, Set[int]]:
    """
    Return:
      1) projected subgraph containing only ancestors of root_id,
         up to max_depth generations
      2) has_more: node_ids at the cut depth that have cached parents
         beyond the projection cut (used for '+' markers)
    """
    projected: PedigreeGraph = {}
    has_more: Set[int] = set()
    visited: Set[int] = set()

    def walk(horse_id: int, depth: int) -> None:
        if horse_id in visited:
            return

        node = graph.get(horse_id)
        if not node:
            return

        visited.add(horse_id)
        projected[horse_id] = node

        father_id = node.get("father_id")
        mother_id = node.get("mother_id")

        father_in_graph = isinstance(father_id, int) and father_id in graph
        mother_in_graph = isinstance(mother_id, int) and mother_id in graph

        # --- projection cut ---
        if depth >= max_depth:
            if father_in_graph or mother_in_graph:
                has_more.add(horse_id)
            return

        if father_in_graph:
            walk(father_id, depth + 1)
        if mother_in_graph:
            walk(mother_id, depth + 1)

    walk(root_id, depth=0)
    return projected, has_more

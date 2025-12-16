from __future__ import annotations

from collections import deque, Counter
from typing import Any


def merged_generation_summary(
    merged_graph: dict[int, dict[str, Any]],
    *,
    root_id: int,
    max_depth: int | None = None,
) -> tuple[dict[str, Any], dict[int, int]]:
    """
    UNIQUE ancestor summary (deduplicated by horse_id).
    Returns:
      summary: {total_nodes, max_generation, open_nodes, closed_nodes}
      gen_counts: {generation: count}
    """
    if root_id not in merged_graph:
        return (
            {"total_nodes": 0, "max_generation": 0, "open_nodes": 0, "closed_nodes": 0},
            {},
        )

    q = deque([(root_id, 0)])
    dist: dict[int, int] = {root_id: 0}

    while q:
        nid, d = q.popleft()
        if max_depth is not None and d >= max_depth:
            continue

        node = merged_graph.get(nid) or {}
        for pid in (node.get("father_id"), node.get("mother_id")):
            if isinstance(pid, int) and pid in merged_graph and pid not in dist:
                dist[pid] = d + 1
                q.append((pid, d + 1))

    gen_counts = Counter(dist.values())

    open_nodes = 0
    closed_nodes = 0
    for nid in dist:
        node = merged_graph.get(nid) or {}
        f = node.get("father_id")
        m = node.get("mother_id")
        f_known = isinstance(f, int) and f in merged_graph
        m_known = isinstance(m, int) and m in merged_graph

        if not f_known and not m_known:
            closed_nodes += 1
        elif not f_known or not m_known:
            open_nodes += 1

    summary = {
        "total_nodes": len(dist),
        "max_generation": max(gen_counts) if gen_counts else 0,
        "open_nodes": open_nodes,
        "closed_nodes": closed_nodes,
    }
    return summary, dict(sorted(gen_counts.items()))


def merged_generation_appearance_summary(
    merged_graph: dict[int, dict[str, Any]],
    *,
    root_id: int,
    max_depth: int,
) -> tuple[dict[int, int], dict[int, int]]:
    """
    APPEARANCE-based summary (does NOT deduplicate).
    Returns:
      appearances_per_gen[g] = number of appearances at generation g
      unique_per_gen[g]      = unique horse_ids at generation g
    """
    if root_id not in merged_graph:
        return {}, {}

    current = [root_id]
    appearances_per_gen: dict[int, int] = {0: 1}
    unique_per_gen: dict[int, int] = {0: 1}

    for gen in range(1, max_depth + 1):
        nxt: list[int] = []
        for hid in current:
            node = merged_graph.get(hid) or {}
            f = node.get("father_id")
            m = node.get("mother_id")

            if isinstance(f, int) and f in merged_graph:
                nxt.append(f)
            if isinstance(m, int) and m in merged_graph:
                nxt.append(m)

        if not nxt:
            break

        appearances_per_gen[gen] = len(nxt)
        unique_per_gen[gen] = len(set(nxt))
        current = nxt

    return appearances_per_gen, unique_per_gen

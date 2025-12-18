from __future__ import annotations

from collections import defaultdict
from typing import Any


def ancestor_influence_scores(
    merged_graph: dict[int, dict[str, Any]],
    *,
    root_id: int,
    max_depth: int,
    include_root: bool = False,
    exp_alpha: float = 0.75,   # slower exponential
    power_p: float = 1.0,      # power-law exponent
    focus_ids: set[int] | None = None,
) -> dict[int, dict[str, float]]:
    """
    Compute per-ancestor influence scores from a merged pedigree graph.

    IMPORTANT: What does "count" mean?

      "count" is an APPEARANCE COUNT (preserves repeats), computed on the
      expanded pedigree tree implied by the merged graph up to max_depth.

      Concretely:
        - We expand generation by generation from root.
        - Each time an ancestor ID appears in the expanded generation list,
          we increment its count by 1.
        - If the same ancestor appears multiple times via different paths
          (inbreeding / duplicate occurrences), it is counted multiple times.

      This is NOT a unique-reachable-node count.

    Notes on non-additivity / intuition traps:
      - Counts are not additive across relatives (e.g., parent + grandsire)
        because the parent's count already includes the grandsire's line.
      - If you compare child vs parent using the SAME max_depth, the child's
        expanded ancestry includes each parent's ancestry only up to depth
        (max_depth - 1) beyond the parent (because the parent itself is at gen=1).
        So "child(max_depth)" aligns to "parent(max_depth-1)" for the parent's
        contribution.
      - Overlap (the same ancestor appearing via multiple paths) also breaks
        naive additivity; this is expected for appearance counts.

    Returned structure (per ancestor horse_id):
      {
        horse_id: {
          "count": float(int),       # appearance count (integer stored as float for compatibility)
          "score_exp": float,        # sum(1 / 2^gen)  [genetic share]
          "score_exp_slow": float,   # sum(alpha^gen)  [deep influence]
          "score_lin": float,        # linear depth decay
          "score_power": float,      # sum(1 / (gen+1)^p)
        }
      }

    If focus_ids is provided, only those horse_ids are included in the output.
    Traversal is unchanged; filtering happens at output time.

    Parent pointer keys:
      - preferred: "father_id" / "mother_id"
      - fallback:  "father" / "mother"
    """
    if root_id not in merged_graph:
        return {}

    def w_lin(gen: int) -> float:
        if gen <= 0:
            return 1.0
        if gen > max_depth:
            return 0.0
        return (max_depth - gen + 1) / max_depth

    def _get_parent_id(node: dict[str, Any], key: str) -> int | None:
        v = node.get(key)
        if isinstance(v, int):
            return v

        if key == "father_id":
            v2 = node.get("father")
            return v2 if isinstance(v2, int) else None
        if key == "mother_id":
            v2 = node.get("mother")
            return v2 if isinstance(v2, int) else None

        return None

    scores = defaultdict(
        lambda: {
            "count": 0.0,
            "score_exp": 0.0,
            "score_exp_slow": 0.0,
            "score_lin": 0.0,
            "score_power": 0.0,
        }
    )

    # "current" is a LIST, not a set: duplicates are preserved and will be expanded
    # and counted in descendants, implementing true appearance counting.
    current = [root_id]

    if include_root:
        scores[root_id]["count"] += 1
        scores[root_id]["score_exp"] += 1.0
        scores[root_id]["score_exp_slow"] += 1.0
        scores[root_id]["score_lin"] += 1.0
        scores[root_id]["score_power"] += 1.0

    for gen in range(1, max_depth + 1):
        nxt: list[int] = []

        for hid in current:
            node = merged_graph.get(hid) or {}

            f = _get_parent_id(node, "father_id")
            m = _get_parent_id(node, "mother_id")

            if isinstance(f, int) and f in merged_graph:
                nxt.append(f)
            if isinstance(m, int) and m in merged_graph:
                nxt.append(m)

        if not nxt:
            break

        w_exp = 1.0 / (2 ** gen)
        w_exp_slow = exp_alpha ** gen
        w_lin_val = w_lin(gen)
        w_pow = 1.0 / ((gen + 1) ** power_p)

        for aid in nxt:
            s = scores[aid]
            s["count"] += 1
            s["score_exp"] += w_exp
            s["score_exp_slow"] += w_exp_slow
            s["score_lin"] += w_lin_val
            s["score_power"] += w_pow

        current = nxt

    out: dict[int, dict[str, float]] = {}

    # If focus_ids is provided, ensure every focus id appears in output
    # even if its scores are all zeros.
    if focus_ids is not None:
        for fid in focus_ids:
            _ = scores[fid]

    for hid, d in scores.items():
        if focus_ids is not None and hid not in focus_ids:
            continue
        out[hid] = {
            "count": float(int(d["count"])),
            "score_exp": float(d["score_exp"]),
            "score_exp_slow": float(d["score_exp_slow"]),
            "score_lin": float(d["score_lin"]),
            "score_power": float(d["score_power"]),
        }

    return out
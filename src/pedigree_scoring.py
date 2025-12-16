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
    Returns per horse_id (appearance-based, no deduplication):

      {
        horse_id: {
          "count": int,
          "score_exp": float,        # sum(1 / 2^gen)  [genetic share]
          "score_exp_slow": float,   # sum(alpha^gen)  [deep influence]
          "score_lin": float,        # linear depth decay
          "score_power": float,      # sum(1 / (gen+1)^p)
        }
      }

    If focus_ids is provided, only those horse_ids are included in the output.
    Traversal is unchanged; filtering happens at output time.
    """
    if root_id not in merged_graph:
        return {}

    def w_lin(gen: int) -> float:
        if gen <= 0:
            return 1.0
        if gen > max_depth:
            return 0.0
        return (max_depth - gen + 1) / max_depth

    scores = defaultdict(
        lambda: {
            "count": 0.0,
            "score_exp": 0.0,
            "score_exp_slow": 0.0,
            "score_lin": 0.0,
            "score_power": 0.0,
        }
    )

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
            f = node.get("father_id")
            m = node.get("mother_id")

            if isinstance(f, int) and f in merged_graph:
                nxt.append(f)
            if isinstance(m, int) and m in merged_graph:
                nxt.append(m)

        if not nxt:
            break

        w_exp = 1.0 / (2 ** gen)
        w_exp_slow = exp_alpha ** gen
        w_lin_val = w_lin(gen)              # ✅ FIXED
        w_pow = 1.0 / ((gen + 1) ** power_p)

        for aid in nxt:
            s = scores[aid]
            s["count"] += 1
            s["score_exp"] += w_exp
            s["score_exp_slow"] += w_exp_slow
            s["score_lin"] += w_lin_val
            s["score_power"] += w_pow

        current = nxt

    # Normalize + optional filtering
    out: dict[int, dict[str, float]] = {}
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
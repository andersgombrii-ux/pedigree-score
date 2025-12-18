from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AsciiNode:
    horse_id: Optional[int]
    father_id: Optional[int]
    mother_id: Optional[int]
    sex: Optional[str]  # "M"/"F"/"male"/"female"/None


def render_pedigree_ascii(
    flat: list[dict] | None = None,
    *,
    graph: dict[int, dict[str, Any]] | None = None,
    root_id: int,
    root_sex: str,  # "X" or "O"
    max_depth: int = 5,
    x_step: int = 4,
    has_more: set[int] | None = None,
) -> str:
    """
    Sideways pedigree. Left -> right is deeper generations.

    Symbols:
      X = male (or father-role fallback)
      O = female (or mother-role fallback)
      ? = unknown HORSE (missing parent placeholder; should only appear at the edge)
      + = deeper cached ancestry exists beyond displayed depth (has_more)

    Note: We do NOT use '?' for "unknown sex". If sex is missing, we fall back to role.
    """
    if root_sex not in ("X", "O"):
        raise ValueError("root_sex must be 'X' or 'O'")

    has_more = has_more or set()

    # Index nodes by horse_id
    by_id: dict[int, AsciiNode] = {}

    if graph is not None:
        for hid, n in graph.items():
            if not isinstance(hid, int):
                continue
            father = n.get("father_id")
            mother = n.get("mother_id")
            by_id[hid] = AsciiNode(
                horse_id=hid,
                father_id=father if isinstance(father, int) else None,
                mother_id=mother if isinstance(mother, int) else None,
                sex=n.get("sex"),
            )
    else:
        flat = flat or []
        for h in flat:
            hid = h.get("horse_id")
            if isinstance(hid, int):
                by_id[hid] = AsciiNode(
                    horse_id=hid,
                    father_id=h.get("father_id") if isinstance(h.get("father_id"), int) else None,
                    mother_id=h.get("mother_id") if isinstance(h.get("mother_id"), int) else None,
                    sex=h.get("sex"),
                )

    def get_node(hid: Optional[int]) -> Optional[AsciiNode]:
        return by_id.get(hid) if isinstance(hid, int) else None

    # --- unknown parent placeholders (so '?' only appears at the edge) ---
    unknown_ids: set[int] = set()
    next_unknown_id = -1

    def new_unknown() -> int:
        nonlocal next_unknown_id
        uid = next_unknown_id
        next_unknown_id -= 1
        unknown_ids.add(uid)
        by_id[uid] = AsciiNode(horse_id=uid, father_id=None, mother_id=None, sex=None)
        return uid

    def normalize_sex(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip().lower()
        if s in ("m", "male", "hingst", "valack", "stallion", "gelding", "x"):
            return "X"
        if s in ("f", "female", "sto", "mare", "o"):
            return "O"
        return None

    # --- layout: compute y positions with a simple recursive tidy layout ---
    next_leaf_y = 0
    pos: dict[tuple[int, int], tuple[int, int]] = {}  # (hid, depth) -> (x, y)
    role: dict[tuple[int, int], str] = {}             # (hid, depth) -> "root"/"father"/"mother"/"unknown"

    def layout(hid: int, depth: int, role_name: str) -> int:
        nonlocal next_leaf_y
        if depth > max_depth:
            return -1

        # Unknown placeholders are always leaves
        if hid in unknown_ids:
            y = next_leaf_y
            next_leaf_y += 2
            pos[(hid, depth)] = (depth * x_step, y)
            role[(hid, depth)] = "unknown"
            return y

        n = get_node(hid)
        f = n.father_id if n else None
        m = n.mother_id if n else None

        # At cut depth: still place node, but do not expand further
        if depth == max_depth:
            y = next_leaf_y
            next_leaf_y += 2
            pos[(hid, depth)] = (depth * x_step, y)
            role[(hid, depth)] = role_name
            return y

        # If a parent is missing, create an unknown placeholder so '?' is visible at the edge
        if f is None:
            f = new_unknown()
        if m is None:
            m = new_unknown()

        fy = layout(f, depth + 1, "father")
        my = layout(m, depth + 1, "mother")

        y = (fy + my) // 2
        pos[(hid, depth)] = (depth * x_step, y)
        role[(hid, depth)] = role_name
        return y

    layout(root_id, 0, "root")

    all_points = list(pos.values())
    if not all_points:
        return ""

    max_x = max(x for x, _ in all_points)
    max_y = max(y for _, y in all_points)

    # +2 columns so we can place the has_more marker to the right of a node symbol
    width = max_x + 2
    height = max_y + 1

    canvas = [[" " for _ in range(width + 1)] for _ in range(height + 1)]

    def put(x: int, y: int, ch: str) -> None:
        if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
            canvas[y][x] = ch

    def symbol_for(hid: int, depth: int) -> str:
        if hid in unknown_ids:
            return "?"
        if hid == root_id and depth == 0:
            return root_sex

        n = get_node(hid)
        s = normalize_sex(n.sex if n else None)
        if s in ("X", "O"):
            return s

        # Sex missing: fall back to pedigree role (father/mother)
        r = role.get((hid, depth), "")
        if r == "father":
            return "X"
        if r == "mother":
            return "O"
        # Fallback shouldn’t really happen, but keep it stable
        return "?"

    def put_symbol(hid: int, depth: int, x: int, y: int) -> None:
        put(x, y, symbol_for(hid, depth))
        # Only mark real (identified) nodes, not unknown placeholders
        if hid not in unknown_ids and hid in has_more and x + 1 < len(canvas[0]):
            put(x + 1, y, "+")  # <-- FIX: use '+' as has_more marker

    def draw_h(x1: int, x2: int, y: int) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if canvas[y][x] == " ":
                canvas[y][x] = "-"

    def draw_v(x: int, y1: int, y2: int) -> None:
        for yy in range(min(y1, y2), max(y1, y2) + 1):
            if canvas[yy][x] == " ":
                canvas[yy][x] = "|"

    def draw_edges(hid: int, depth: int) -> None:
        if depth >= max_depth:
            return

        n = get_node(hid)
        # Unknown placeholders have no edges
        if hid in unknown_ids:
            return
        if not n:
            return

        x0, y0 = pos[(hid, depth)]
        jx = x0 + 2  # join column

        # Father
        f = n.father_id if n.father_id is not None else None
        # But we created placeholders during layout, so use those if needed:
        if f is None:
            f = new_unknown()

        # Mother
        m = n.mother_id if n.mother_id is not None else None
        if m is None:
            m = new_unknown()

        if (f, depth + 1) in pos:
            fx, fy = pos[(f, depth + 1)]
            draw_h(jx, fx - 1, fy)
            draw_v(jx, y0, fy)
            put_symbol(f, depth + 1, fx, fy)
            draw_edges(f, depth + 1)

        if (m, depth + 1) in pos:
            mx, my = pos[(m, depth + 1)]
            draw_h(jx, mx - 1, my)
            draw_v(jx, y0, my)
            put_symbol(m, depth + 1, mx, my)
            draw_edges(m, depth + 1)

    # Root
    rx, ry = pos[(root_id, 0)]
    put_symbol(root_id, 0, rx, ry)
    draw_edges(root_id, 0)

    lines = ["".join(row).rstrip() for row in canvas]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
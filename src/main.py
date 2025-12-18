from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from .travsport_api import (
    build_client,
    resolve_horse,
    fetch_pedigree_html,
)

from .pedigree_summary import (
    merged_generation_summary,
    merged_generation_appearance_summary,
)

from .pedigree_parser import extract_pedigree
from .lineage_utils import flatten_tree
from .birthyear_utils import enrich_birth_years
from .age_gap import compute_age_gaps
from .corrections import apply_manual_corrections

from .pedigree_scoring import ancestor_influence_scores

# local cache dir
from .pedigree_store import (
    DEFAULT_CACHE_DIR,
)

# merged graph + projection
from .pedigree_graph import build_merged_pedigree_graph
from .pedigree_projection import project_ancestry

# merged graph persistence
from .pedigree_graph_store import (
    load_merged_graph,
    save_merged_graph,
)

# ASCII pedigree renderer
from .pedigree_ascii import render_pedigree_ascii

# NEW: XLSX export/append
from .scores_xlsx import append_scores_row

if TYPE_CHECKING:
    from .travsport_api import HorseIdentity


# ---------------------------------------------------------------------------
# Cache versioning
# ---------------------------------------------------------------------------

CACHE_VERSION = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cache_file_for_root(root_id: Optional[int]) -> Optional[Path]:
    if root_id is None:
        return None
    return DEFAULT_CACHE_DIR / f"{root_id}.json"


def _read_versioned_cache(path: Path) -> Optional[dict[str, Any]]:
    """
    Cache file format:
      {
        "cache_version": <int>,
        "created_at": "<iso>",
        "root_id": <int>,
        "horses": [ ... flat list ... ]
      }
    """
    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        if obj.get("cache_version") != CACHE_VERSION:
            return None
        horses = obj.get("horses")
        if not isinstance(horses, list):
            return None
        return obj
    except Exception:
        return None


def _write_versioned_cache(path: Path, root_id: int, horses: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    obj = {
        "cache_version": CACHE_VERSION,
        "created_at": _utc_now_iso(),
        "root_id": root_id,
        "horses": horses,
    }
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and inspect a pedigree from travsport.se (with merged-cache analysis).",
    )

    parser.add_argument("--name", required=False)
    parser.add_argument("--year", type=int, default=None)

    parser.add_argument("--save-html", metavar="PATH")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--skip-age-gaps", action="store_true")

    # merged summary + depth controls
    parser.add_argument(
        "--merged-summary",
        action="store_true",
        help="Show merged-cache summary (unique + appearances + influence scoring). "
             "If --name is omitted, this runs in global-only mode.",
    )
    parser.add_argument(
        "--summary-max-depth",
        type=int,
        default=None,
        help="Optional depth cap for merged UNIQUE summary BFS (default: unlimited).",
    )
    parser.add_argument(
        "--appearance-max-depth",
        type=int,
        default=12,
        help="Depth cap for appearance-based generation summary + scoring (default: 12).",
    )

    parser.add_argument(
        "--focus-ancestors",
        type=str,
        default=None,
        help="Comma-separated list of ancestor IDs and/or names to focus influence output on "
             "(e.g. '12345,Varenne' or 'Dalterna,Grasiös'). "
             "Name matching is case-insensitive and ignores trailing '(...)' suffixes like '(NO)'.",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Depth cap for ASCII projection (default: 10).",
    )

    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore any existing cached pedigree and rebuild it (overwrites cache).",
    )
    parser.add_argument(
        "--show-cache",
        action="store_true",
        help="Show whether a cached pedigree exists for this horse (requires --name).",
    )

    # NEW: Append scores to XLSX table
    parser.add_argument(
        "--append-scores",
        action="store_true",
        help="Append one row per queried horse to an Excel file (scores table).",
    )
    parser.add_argument(
        "--scores-xlsx",
        type=str,
        default="scores.xlsx",
        help="Path to scores Excel file (default: scores.xlsx).",
    )
    parser.add_argument(
        "--scores-sheet",
        type=str,
        default="Scores",
        help="Worksheet name in the scores Excel file (default: Scores).",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------

def print_pedigree_summary(tree) -> None:
    print("\n[main] Parsed pedigree tree")
    print("-" * 60)
    print(f"Root horse: {tree.root_name}")
    print(f"Max generations: {tree.max_generations}")
    print(f"Total nodes: {len(tree.nodes)}")

    counts = Counter(n.generation for n in tree.nodes)
    for g in sorted(counts):
        print(f"  Generation {g}: {counts[g]} nodes")


def _normalize_root_horse_id(horse: HorseIdentity) -> Optional[int]:
    hid = horse.horse_id
    if isinstance(hid, str) and hid.isdigit():
        return int(hid)
    if isinstance(hid, int):
        return hid
    return None


def _get_or_build_merged_graph() -> dict[int, dict[str, Any]]:
    """
    Load merged graph from disk if present; otherwise build and persist it.
    """
    merged_graph = load_merged_graph()
    if merged_graph is not None:
        print(f"[main] Merged graph: loaded (nodes={len(merged_graph)})")
        return merged_graph

    merged_graph = build_merged_pedigree_graph()
    print(f"[main] Merged graph: built (nodes={len(merged_graph)})")
    try:
        save_merged_graph(merged_graph)
        print("[main] Merged graph: saved")
    except Exception as e:
        print("[main] WARNING: failed to save merged graph:", e)

    return merged_graph


def _parse_focus_tokens(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


_PARENS_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_TRAILING_REGCODE_RE = re.compile(r"\s*(?:TS|T)\s*[- ]?\s*\d+\s*$", re.IGNORECASE)


def _normalize_name_for_match(name: str) -> str:
    """
    Normalize a horse name for focus matching:
      - take first line only
      - strip whitespace
      - remove trailing '(...)' suffixes like '(NO)'
      - remove trailing registry codes like 'T-275', 'TS123'
      - remove '*' marker(s)
      - collapse internal whitespace
      - casefold
    """
    s = name.splitlines()[0].strip()
    s = s.replace("*", "").strip()
    s = _PARENS_SUFFIX_RE.sub("", s).strip()
    s = _TRAILING_REGCODE_RE.sub("", s).strip()
    s = " ".join(s.split())
    return s.casefold()


def _is_likely_synthetic_id(hid: int) -> bool:
    """
    Heuristic for IDs that are likely generated locally (e.g., hash-based placeholders).
    """
    return hid < 0 and abs(hid) > 1_000_000


def _prefer_canonical_ids(ids: list[int]) -> list[int]:
    """
    Prefer non-synthetic IDs when possible.
    """
    if len(ids) <= 1:
        return ids

    non_synth = [i for i in ids if not _is_likely_synthetic_id(i)]
    if non_synth:
        return non_synth
    return ids


def _resolve_focus_ancestors(
    merged_graph: dict[int, dict[str, Any]],
    tokens: list[str],
) -> set[int]:
    """
    Resolve focus tokens to horse_ids (combined).
    """
    if not tokens:
        return set()

    name_to_ids: dict[str, list[int]] = {}
    all_names: list[tuple[str, int]] = []

    for hid, node in merged_graph.items():
        nm = node.get("name") or node.get("horse_name") or node.get("root_name")
        if isinstance(nm, str) and nm.strip():
            key = _normalize_name_for_match(nm)
            name_to_ids.setdefault(key, []).append(hid)
            all_names.append((key, hid))

    resolved: set[int] = set()

    for tok in tokens:
        if tok.isdigit():
            resolved.add(int(tok))
            continue

        tok_key = _normalize_name_for_match(tok)

        ids = name_to_ids.get(tok_key, [])
        if ids:
            uniq = sorted(set(ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok!r} matched multiple IDs: {uniq} (pref: {preferred})")
            resolved.update(preferred)
            continue

        prefix_ids = [hid for key, hid in all_names if key.startswith(tok_key)]
        if prefix_ids:
            uniq = sorted(set(prefix_ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok!r} prefix-matched multiple IDs: {uniq} (pref: {preferred})")
            resolved.update(preferred)
            continue

        contains_ids = [hid for key, hid in all_names if tok_key in key]
        if contains_ids:
            uniq = sorted(set(contains_ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok!r} contained-match multiple IDs: {uniq} (pref: {preferred})")
            resolved.update(preferred)
            continue

        print(f"[main] WARNING: focus ancestor not found by name: {tok!r}")

    return resolved


def _resolve_focus_ancestor_map(
    merged_graph: dict[int, dict[str, Any]],
    tokens: list[str],
) -> dict[str, set[int]]:
    """
    Resolve focus tokens -> set[horse_id] PER TOKEN (so we can create per-ancestor columns).
    If a token resolves to multiple ids, we keep them all (with canonical preference).
    If not found, token maps to empty set().
    """
    if not tokens:
        return {}

    name_to_ids: dict[str, list[int]] = {}
    all_names: list[tuple[str, int]] = []

    for hid, node in merged_graph.items():
        nm = node.get("name") or node.get("horse_name") or node.get("root_name")
        if isinstance(nm, str) and nm.strip():
            key = _normalize_name_for_match(nm)
            name_to_ids.setdefault(key, []).append(hid)
            all_names.append((key, hid))

    out: dict[str, set[int]] = {}

    for tok in tokens:
        tok_clean = tok.strip()
        if not tok_clean:
            continue

        if tok_clean.isdigit():
            out[tok_clean] = {int(tok_clean)}
            continue

        tok_key = _normalize_name_for_match(tok_clean)

        ids = name_to_ids.get(tok_key, [])
        if ids:
            uniq = sorted(set(ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok_clean!r} matched multiple IDs: {uniq} (pref: {preferred})")
            out[tok_clean] = set(preferred)
            continue

        prefix_ids = [hid for key, hid in all_names if key.startswith(tok_key)]
        if prefix_ids:
            uniq = sorted(set(prefix_ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok_clean!r} prefix-matched multiple IDs: {uniq} (pref: {preferred})")
            out[tok_clean] = set(preferred)
            continue

        contains_ids = [hid for key, hid in all_names if tok_key in key]
        if contains_ids:
            uniq = sorted(set(contains_ids))
            preferred = sorted(set(_prefer_canonical_ids(uniq)))
            if len(uniq) > 1:
                print(f"[main] WARNING: focus ancestor name {tok_clean!r} contained-match multiple IDs: {uniq} (pref: {preferred})")
            out[tok_clean] = set(preferred)
            continue

        print(f"[main] WARNING: focus ancestor not found by name: {tok_clean!r}")
        out[tok_clean] = set()

    return out


# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    cache_enabled = not args.no_cache

    # Keep stdout JSON-clean for --json pipelines
    real_stdout = sys.stdout
    if args.json:
        sys.stdout = sys.stderr

    def _log(*a: Any) -> None:
        print(*a, file=sys.stderr if args.json else sys.stdout)

    try:
        # ------------------------------------------------------------
        # Global-only mode
        # ------------------------------------------------------------
        if args.name is None:
            if not args.merged_summary:
                raise SystemExit("[main] ERROR: --name is required unless --merged-summary is used")

            merged_graph = _get_or_build_merged_graph()
            _log(f"[main] Merged graph nodes: {len(merged_graph)}")
            _log("\n[main] Pipeline completed.")
            return

        # From here on, we have a root horse context
        _log(f"[main] Looking up horse: {args.name!r} year={args.year!r}")

        session = build_client()

        try:
            horse: HorseIdentity = resolve_horse(session, args.name, args.year)  # type: ignore
        except Exception as e:
            _log("[main] ERROR resolving horse:", e)
            return

        _log(
            f"[main] Resolved: horse_id={horse.horse_id!r}, "
            f"name={horse.name!r}, birth_year={horse.birth_year!r}"
        )

        root_id = _normalize_root_horse_id(horse)
        cache_path = _cache_file_for_root(root_id)

        # ---- Show cache status (informational only) ----
        if args.show_cache:
            if cache_path is None:
                _log("[main] No numeric horse_id, cannot map to cache file")
            elif cache_path.exists():
                obj = _read_versioned_cache(cache_path)
                if obj is None:
                    _log(f"[main] Cache exists but is incompatible (version mismatch): {cache_path}")
                else:
                    _log(f"[main] Cache exists (v{obj.get('cache_version')}): {cache_path}")
            else:
                _log("[main] No cache found for this horse")

        # ---- Try cache (JSON OR ASCII) ----
        cache_used = False
        flat: Optional[list[dict]] = None

        if (
            (args.json or args.ascii or args.append_scores)
            and cache_enabled
            and not args.refresh_cache
            and root_id is not None
            and cache_path is not None
        ):
            cached = _read_versioned_cache(cache_path)
            if cached is not None:
                flat = cached["horses"]
                cache_used = True
                _log(f"[main] Cache hit ({len(flat)} nodes) v{cached.get('cache_version')}")

        # ---- Fetch + parse if needed ----
        tree = None

        if flat is None:
            try:
                html = fetch_pedigree_html(session, horse)
            except Exception as e:
                _log("[main] ERROR fetching pedigree:", e)
                return

            if args.save_html:
                try:
                    with open(args.save_html, "w", encoding="utf-8") as f:
                        f.write(html)
                except Exception as e:
                    _log("[main] WARNING saving HTML:", e)

            try:
                tree = extract_pedigree(html, max_generation=5)
                tree.root.name = horse.name
                if root_id is not None:
                    tree.root.horse_id = root_id
            except Exception as e:
                _log("[main] ERROR parsing pedigree:", e)
                return

            flat = flatten_tree(tree)
            flat = enrich_birth_years(flat, session)
            flat = apply_manual_corrections(flat)

            if (args.json or args.ascii or args.append_scores) and cache_enabled and root_id is not None and cache_path is not None:
                try:
                    _write_versioned_cache(cache_path, root_id, flat)
                    _log(f"[main] Cache saved (v{CACHE_VERSION}) -> {cache_path}")
                except Exception as e:
                    _log("[main] WARNING: failed to save cache:", e)

        assert flat is not None

        # -------------------------------------------------------------------
        # NEW: Append scores row to XLSX (one row per query)
        # -------------------------------------------------------------------
        if args.append_scores:
            focus_tokens = _parse_focus_tokens(args.focus_ancestors)
            if not focus_tokens:
                raise SystemExit("[main] ERROR: --append-scores requires --focus-ancestors with at least one ancestor name")

            if root_id is None:
                # You said "HorseId (if available) + Name + BirthYear" – but root_id should normally exist.
                # We still allow append; HorseId cell becomes blank/None.
                _log("[main] WARNING: root horse_id missing; XLSX key will fall back to Name+BirthYear")

            merged_graph = _get_or_build_merged_graph()

            # per-token -> ids, plus union for scoring call
            token_to_ids = _resolve_focus_ancestor_map(merged_graph, focus_tokens)
            focus_ids_union: set[int] = set()
            for ids in token_to_ids.values():
                focus_ids_union.update(ids)

            # If nothing resolves, we still want a row with zeros.
            influence = ancestor_influence_scores(
                merged_graph,
                root_id=root_id if root_id is not None else int(horse.horse_id) if str(horse.horse_id).isdigit() else 0,
                max_depth=args.appearance_max_depth,
                include_root=False,
                focus_ids=focus_ids_union if focus_ids_union else None,
            )

            # Build per-token values (missing -> 0)
            per_token: dict[str, dict[str, float]] = {}
            for tok in focus_tokens:
                ids = token_to_ids.get(tok, set())
                score_exp = 0.0
                score_slow = 0.0
                count = 0.0

                for hid in ids:
                    d = influence.get(hid)
                    if not d:
                        continue
                    score_exp += float(d.get("score_exp", 0.0))
                    score_slow += float(d.get("score_exp_slow", 0.0))
                    count += float(d.get("count", 0.0))

                per_token[tok] = {
                    "score_exp": score_exp,
                    "score_exp_slow": score_slow,
                    "count": count,
                }

            append_scores_row(
                xlsx_path=Path(args.scores_xlsx),
                sheet_name=args.scores_sheet,
                horse_id=root_id,
                horse_name=horse.name,
                birth_year=horse.birth_year,
                focus_ancestors=focus_tokens,
                per_ancestor=per_token,
            )
            _log(f"[main] Scores appended -> {args.scores_xlsx} [{args.scores_sheet}]")

        # -------------------------------------------------------------------
        # ---- Merged-cache generation summary (unique + appearances + scoring)
        # -------------------------------------------------------------------
        merged_graph: dict[int, dict[str, Any]] | None = None

        if args.merged_summary and root_id is not None:
            merged_graph = _get_or_build_merged_graph()
            _log(f"[main] Merged graph nodes: {len(merged_graph)}")

            def label(hid: int) -> str:
                node = merged_graph.get(hid, {}) if merged_graph else {}
                name = node.get("name") or node.get("horse_name") or node.get("root_name")
                if isinstance(name, str) and name.strip():
                    return f"{name} ({hid})"
                return str(hid)

            summary, gen_counts = merged_generation_summary(
                merged_graph,
                root_id=root_id,
                max_depth=args.summary_max_depth,
            )

            _log("\n[main] Merged Pedigree Summary (unique ancestors)")
            _log("-" * 60)
            _log(f"Total unique nodes (reachable): {summary['total_nodes']}")
            _log(f"Max generation (unique): {summary['max_generation']}")
            _log(f"Open nodes: {summary['open_nodes']}")
            _log(f"Closed nodes: {summary['closed_nodes']}\n")
            for g, c in gen_counts.items():
                _log(f"  Generation {g}: {c} unique nodes")

            appearances_per_gen, unique_per_gen = merged_generation_appearance_summary(
                merged_graph,
                root_id=root_id,
                max_depth=args.appearance_max_depth,
            )

            _log("\n[main] Pedigree Appearance Summary (preserves repeats)")
            _log("-" * 60)
            max_g = max(appearances_per_gen.keys()) if appearances_per_gen else 0
            for g in range(0, max_g + 1):
                a = appearances_per_gen.get(g, 0)
                u = unique_per_gen.get(g, 0)
                ratio = (u / a) if a else 0.0
                _log(f"  Generation {g}: appearances={a} unique={u} compression={ratio:.2f}")

            focus_tokens = _parse_focus_tokens(args.focus_ancestors)
            focus_ids = _resolve_focus_ancestors(merged_graph, focus_tokens) if focus_tokens else None
            if focus_ids is not None:
                _log(f"[main] Focus ancestors resolved: {len(focus_ids)} ids")

            influence = ancestor_influence_scores(
                merged_graph,
                root_id=root_id,
                max_depth=args.appearance_max_depth,
                include_root=False,
                focus_ids=focus_ids,
            )

            top_n = 25

            def top_by(key: str) -> list[tuple[int, dict[str, float]]]:
                return sorted(
                    influence.items(),
                    key=lambda kv: kv[1].get(key, 0.0),
                    reverse=True,
                )[:top_n]

            _log("\n[main] Top ancestors by SIMPLE COUNT (appearances)")
            _log("-" * 60)
            for hid, d in top_by("count"):
                _log(f"  {label(hid)}: count={int(d['count'])}")

            _log("\n[main] Top ancestors by LINEAR DECAY score")
            _log("-" * 60)
            for hid, d in top_by("score_lin"):
                _log(f"  {label(hid)}: score_lin={d['score_lin']:.6f} (count={int(d['count'])})")

            if influence and "score_power" in next(iter(influence.values())):
                _log("\n[main] Top ancestors by POWER-LAW score")
                _log("-" * 60)
                for hid, d in top_by("score_power"):
                    _log(f"  {label(hid)}: score_power={d['score_power']:.9f} (count={int(d['count'])})")

            _log("\n[main] Top ancestors by EXPONENTIAL contribution score")
            _log("-" * 60)
            for hid, d in top_by("score_exp"):
                _log(f"  {label(hid)}: score_exp={d['score_exp']:.9f} (count={int(d['count'])})")

            if influence and "score_exp_slow" in next(iter(influence.values())):
                _log("\n[main] Top ancestors by SLOW EXPONENTIAL decay (deep influence)")
                _log("-" * 60)
                for hid, d in top_by("score_exp_slow"):
                    _log(f"  {label(hid)}: score_exp_slow={d['score_exp_slow']:.9f} (count={int(d['count'])})")

        # -------------------------------------------------------------------
        # ---- ASCII pedigree (MERGED CACHE + PROJECTION) ----
        # -------------------------------------------------------------------
        if args.ascii and root_id is not None:
            if merged_graph is None:
                merged_graph = _get_or_build_merged_graph()
                _log(f"[main] Merged graph nodes: {len(merged_graph)}")

            max_depth = args.max_depth
            subgraph, has_more = project_ancestry(
                merged_graph,
                root_id=root_id,
                max_depth=max_depth,
            )

            _log("\n[main] ASCII pedigree (merged cache)\n")
            _log(
                render_pedigree_ascii(
                    graph=subgraph,
                    root_id=root_id,
                    root_sex="X",
                    max_depth=max_depth,
                    has_more=has_more,
                )
            )

        # ---- JSON output ----
        if args.json:
            result: dict = {
                "root_horse": {
                    "horse_id": horse.horse_id,
                    "name": horse.name,
                    "birth_year": horse.birth_year,
                },
                "horses": flat,
                "cache": {
                    "used": cache_used,
                    "path": str(cache_path) if cache_path else None,
                    "cache_version": CACHE_VERSION,
                    "refreshed": bool(args.refresh_cache),
                },
            }

            summary_json = {
                "total_horses": len(flat),
                "known_birth_years": sum(1 for h in flat if h.get("birth_year") is not None),
                "unknown_birth_years": sum(1 for h in flat if h.get("birth_year") is None),
            }

            if not args.skip_age_gaps:
                age_gaps = compute_age_gaps(flat)
                result["age_gaps"] = age_gaps

                def cls(g): return str(g.get("classification", "")).lower()

                summary_json.update(
                    {
                        "age_gap_normal": sum(1 for g in age_gaps if cls(g) == "normal"),
                        "age_gap_very_unusual": sum(1 for g in age_gaps if cls(g) == "very_unusual"),
                        "age_gap_impossible": sum(1 for g in age_gaps if cls(g) == "impossible"),
                        "age_gap_unknown": sum(1 for g in age_gaps if cls(g) == "unknown"),
                    }
                )

            result["summary"] = summary_json

            # Restore real stdout JUST for JSON output
            sys.stdout = real_stdout
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.stdout = sys.stderr
            _log("\n[main] Pipeline completed.")
            return

        # ---- Text summary ----
        if not args.merged_summary and tree is not None:
            print_pedigree_summary(tree)

        _log("\n[main] Pipeline completed.")

    finally:
        sys.stdout = real_stdout


if __name__ == "__main__":
    main()
from __future__ import annotations

from src.pedigree_scoring import ancestor_influence_scores


def test_count_is_true_appearance_count_preserves_repeats() -> None:
    # Construct inbreeding-style repeat:
    # root(1) parents (2,3)
    # both parents share father (9), so 9 appears twice at gen=2 for root=1
    merged_graph = {
        1: {"father_id": 2, "mother_id": 3},
        2: {"father_id": 9, "mother_id": 10},
        3: {"father_id": 9, "mother_id": 11},
        9: {"father_id": None, "mother_id": None},
        10: {"father_id": None, "mother_id": None},
        11: {"father_id": None, "mother_id": None},
    }

    out = ancestor_influence_scores(merged_graph, root_id=1, max_depth=2, focus_ids={9})
    assert 9 in out
    # At gen=2, 9 appears twice => count must be 2
    assert out[9]["count"] == 2.0


def test_child_count_not_less_than_parent_when_depth_allows() -> None:
    # Simple clean tree (no overlap):
    # child(1) -> parent(2) -> ancestor(9)
    merged_graph = {
        1: {"father_id": 2, "mother_id": 3},
        2: {"father_id": 9, "mother_id": 10},
        3: {"father_id": 11, "mother_id": 12},
        9: {"father_id": None, "mother_id": None},
        10: {"father_id": None, "mother_id": None},
        11: {"father_id": None, "mother_id": None},
        12: {"father_id": None, "mother_id": None},
    }

    # Parent sees ancestor 9 at depth=1
    parent = ancestor_influence_scores(merged_graph, root_id=2, max_depth=1, focus_ids={9})
    assert parent[9]["count"] == 1.0

    # Child sees ancestor 9 at depth=2 (through parent) => should be >= parent's
    child = ancestor_influence_scores(merged_graph, root_id=1, max_depth=2, focus_ids={9})
    assert child[9]["count"] >= parent[9]["count"]
    assert child[9]["count"] == 1.0
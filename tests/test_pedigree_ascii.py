from src.pedigree_ascii import render_pedigree_ascii


def test_render_pedigree_ascii_basic():
    """
    Minimal sanity test for ASCII pedigree rendering.
    """

    # Fake flattened pedigree (very small, uneven depth)
    flat = [
        # root
        {
            "horse_id": 1,
            "father_id": 2,
            "mother_id": 3,
            "sex": "male",
        },
        # parents
        {
            "horse_id": 2,
            "father_id": 4,
            "mother_id": None,
            "sex": "male",
        },
        {
            "horse_id": 3,
            "father_id": None,
            "mother_id": None,
            "sex": "female",
        },
        # one grandparent only (uneven depth)
        {
            "horse_id": 4,
            "father_id": None,
            "mother_id": None,
            "sex": "male",
        },
    ]

    ascii_output = render_pedigree_ascii(
        flat=flat,
        root_id=1,
        root_sex="X",
        max_depth=4,
    )

    # Output should not be empty
    assert ascii_output.strip() != ""

    # Should only contain allowed characters
    allowed = set("XO?|\n _/-*")
    assert set(ascii_output).issubset(allowed)

    # Should contain at least one male and one female marker
    assert "X" in ascii_output
    assert "O" in ascii_output


def test_render_pedigree_ascii_uneven_depth():
    """
    Ensure uneven ancestry depth is visible in ASCII output.
    """

    flat = [
        {"horse_id": 1, "father_id": 2, "mother_id": 3, "sex": "male"},
        {"horse_id": 2, "father_id": 4, "mother_id": None, "sex": "male"},
        {"horse_id": 3, "father_id": None, "mother_id": None, "sex": "female"},
        {"horse_id": 4, "father_id": 5, "mother_id": None, "sex": "male"},
        {"horse_id": 5, "father_id": None, "mother_id": None, "sex": "male"},
    ]

    ascii_output = render_pedigree_ascii(
        flat=flat,
        root_id=1,
        root_sex="X",
        max_depth=6,
    )

    lines = [ln for ln in ascii_output.splitlines() if ln.strip()]
    indent_levels = [len(line) - len(line.lstrip(" ")) for line in lines]
    assert max(indent_levels) > min(indent_levels)


def test_render_pedigree_ascii_has_more_marks_plus():
    """
    Nodes listed in has_more should get a '+' marker (X+ / O+).
    """

    flat = [
        {"horse_id": 1, "father_id": 2, "mother_id": 3, "sex": "male"},
        {"horse_id": 2, "father_id": 4, "mother_id": None, "sex": "male"},
        {"horse_id": 3, "father_id": None, "mother_id": None, "sex": "female"},
        {"horse_id": 4, "father_id": None, "mother_id": None, "sex": "male"},
    ]

    ascii_output = render_pedigree_ascii(
        flat=flat,
        root_id=1,
        root_sex="X",
        max_depth=4,
        has_more={2},  # mark father as having deeper cached ancestry
    )

    # Either "X+" appears (preferred) or at least a '+' exists.
    assert "X+" in ascii_output or "+" in ascii_output
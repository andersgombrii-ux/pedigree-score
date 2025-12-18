from src.pedigree_parser import _derive_id_from_registration_number

def test_t_regno_derives_negative_id():
    assert _derive_id_from_registration_number("T-275") == -275
    assert _derive_id_from_registration_number("T–275") == -275  # en-dash
    assert _derive_id_from_registration_number("T−275") == -275  # minus
    assert _derive_id_from_registration_number(" T - 275 ") == -275
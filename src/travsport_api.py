# src/travsport_api.py

from dataclasses import dataclass
from typing import Optional, List
import requests


# -------------------------------
# Data Models (API-facing)
# -------------------------------

@dataclass
class HorseIdentity:
    """
    The resolved identity of a single horse from Travsport.
    """
    horse_id: str
    name: str
    birth_year: Optional[int]


# -------------------------------
# HTTP Client Builder
# -------------------------------

def build_client() -> requests.Session:
    """
    Build and return a configured HTTP session for Travsport API calls.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "pedigree-score/1.0",
        "Accept": "application/json",
    })
    return session


# -------------------------------
# Horse Resolution (REAL API)
# -------------------------------

SEARCH_URL = (
    "https://api.travsport.se/webapi/horses/search/organisation/TROT"
)


def resolve_horse(
    session: requests.Session,
    name: str,
    year: Optional[int],
) -> HorseIdentity:
    """
    Resolve a horse by name (+ optional birth year) using Travsport's search API.

    - If exactly one candidate matches the name, we take it.
    - If multiple candidates match the name and a birth year is provided,
      we select the one whose yearOfBirth matches that year.
    - If multiple remain even after year filter -> error (ambiguous).
    - If none match -> error.
    """

    print("[travsport_api] Searching horse via Travsport API...")

    params = {
        "horseName": name,
        # we keep other filters broad so we don't accidentally hide matches
        "age": 0,              # 0 == all ages
        "gender": "BOTH",
        "trotBreed": "ALL",
        "autoSuffixWildcard": "true",
    }

    resp = session.get(SEARCH_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"Unexpected search response structure: expected list, got {type(data)}"
        )

    # Normalise query name for case-insensitive comparison
    query_norm = name.strip().casefold()

    def norm(s: str) -> str:
        return s.strip().casefold()

    # 1) Filter by name (case-insensitive, substring match)
    candidates: List[dict] = [
        h for h in data
        if query_norm in norm(h.get("name", ""))
    ]

    if not candidates:
        raise RuntimeError(f"No horses found matching name '{name}'")

    # 2) If year is provided, filter by yearOfBirth
    chosen: dict

    if year is not None:
        matches_with_year: List[dict] = []
        for h in candidates:
            raw_year = h.get("yearOfBirth")
            try:
                api_year = int(raw_year) if raw_year is not None else None
            except (TypeError, ValueError):
                api_year = None

            if api_year == year:
                matches_with_year.append(h)

        if not matches_with_year:
            raise RuntimeError(
                f"No horse named '{name}' found with birth year {year}"
            )

        if len(matches_with_year) > 1:
            raise RuntimeError(
                f"Multiple horses named '{name}' found with year {year}; "
                f"cannot pick one deterministically."
            )

        chosen = matches_with_year[0]
    else:
        # No year provided
        if len(candidates) > 1:
            # Force user to disambiguate
            years = ", ".join(
                str(h.get("yearOfBirth")) for h in candidates
            )
            raise RuntimeError(
                f"Multiple horses named '{name}' found (years: {years}). "
                f"Please re-run with --year=YYYY to disambiguate."
            )
        chosen = candidates[0]

    # Safely parse birth year for the HorseIdentity
    birth_year_int: Optional[int]
    raw_year = chosen.get("yearOfBirth")
    try:
        birth_year_int = int(raw_year) if raw_year is not None else None
    except (TypeError, ValueError):
        birth_year_int = None

    return HorseIdentity(
        horse_id=str(chosen["horseId"]),
        name=chosen.get("name", name),
        birth_year=birth_year_int,
    )

# -------------------------------
# Pedigree Fetch (STUB — NEXT STEP)
# -------------------------------

def fetch_pedigree_html(
    session: requests.Session,
    horse: HorseIdentity,
) -> str:
    """
    STUB: This will later fetch the printable 5-generation pedigree HTML.
    """

    print("[travsport_api] fetch_pedigree_html() called (stub)")
    print(f"  horse_id = {horse.horse_id}")

    return "<html><body><h1>FAKE PEDIGREE PAGE</h1></body></html>"
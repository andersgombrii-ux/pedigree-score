from __future__ import annotations

import json
import re
import html as html_lib
from typing import Optional

import requests

# Endpoints
PROFILE_URL = "https://sportapp.travsport.se/sportinfo/horse/ts{}"
PRINTPEDIGREE_URL = "https://sportapp.travsport.se/sportinfo/horse/ts{}/printpedigree"


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_profile_html(session: requests.Session, horse_id: int) -> Optional[str]:
    """
    Fetch the main horse profile page HTML.
    This page contains the 'Mer info' section with 'Född'.
    """
    url = PROFILE_URL.format(horse_id)
    resp = session.get(url, timeout=20)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text


def fetch_printpedigree_html(session: requests.Session, horse_id: int) -> Optional[str]:
    """
    Fetch the printpedigree page HTML for the given horse_id.
    Used only as a secondary source (JSON dateOfBirth) if needed.
    """
    url = PRINTPEDIGREE_URL.format(horse_id)
    resp = session.get(url, timeout=20)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Helpers: HTML → text
# ---------------------------------------------------------------------------

def _html_to_text(html: str) -> str:
    """
    Roughly convert HTML to visible-ish text:
      - unescape entities (&ouml; → ö)
      - strip tags
      - collapse whitespace
    """
    text = html_lib.unescape(html)
    text = re.sub(r"<[^>]+>", " ", text)   # remove tags
    text = re.sub(r"\s+", " ", text)       # collapse whitespace
    return text


# ---------------------------------------------------------------------------
# 1) Primary source: profile page "Född" block
# ---------------------------------------------------------------------------

def extract_birth_year_from_profile_html(html: str) -> Optional[int]:
    """
    Extract birth year from the FULL horse profile page by scanning for
    the Swedish 'Född' label, e.g. (your screenshot):

        <h2>Född</h2>
        <span>1994-06-23 (död 2020)</span>

    After tag stripping this becomes something like:
        "... Född 1994-06-23 (död 2020) ..."
    """
    if not html:
        return None

    text = _html_to_text(html)

    # Look for 'Född' followed by a YYYY-MM-DD within a small window
    m = re.search(
        r"F[öo]dd[^0-9]{0,40}((?:18|19|20)\d{2})-\d{2}-\d{2}",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        # Fallback: just a year after 'Född'
        m = re.search(
            r"F[öo]dd[^0-9]{0,40}((?:18|19|20)\d{2})",
            text,
            flags=re.IGNORECASE,
        )

    if m:
        try:
            year = int(m.group(1))
        except ValueError:
            return None
        if 1800 <= year <= 2100:
            return year

    return None


# ---------------------------------------------------------------------------
# 2) Secondary source: dateOfBirth JSON on printpedigree page
# ---------------------------------------------------------------------------

def extract_birth_year_from_dateofbirth_field(html: str) -> Optional[int]:
    """
    Extract birth year from any 'dateOfBirth' / 'dateOfBirthDisplayValue'
    JSON-like fields present anywhere in the HTML, e.g.:

        ...\"dateOfBirth\":\"1994-06-23\"...
        ..."dateOfBirth":"1994-06-23"...

    We don't care about exact quoting/escaping, only:
        'dateOfBirth' + (some non-digits) + YYYY-MM-DD
    """
    if not html:
        return None

    m = re.search(
        r"dateOfBirth[^0-9]{0,40}((?:18|19|20)\d{2})-\d{2}-\d{2}",
        html,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"dateOfBirthDisplayValue[^0-9]{0,40}((?:18|19|20)\d{2})-\d{2}-\d{2}",
            html,
            flags=re.IGNORECASE,
        )

    if m:
        try:
            year = int(m.group(1))
        except ValueError:
            return None
        if 1800 <= year <= 2100:
            return year

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_birth_year(session: requests.Session, horse_id: Optional[int]) -> Optional[int]:
    """
    High-level helper used by the lineage pipeline.

    Priority:
      1) Profile page 'Född' (Mer info)  → authoritative, avoids Hästpass.
      2) Printpedigree JSON dateOfBirth / dateOfBirthDisplayValue.
      3) Otherwise: None (do NOT guess from Hästpass or other random dates).
    """
    if not horse_id:
        return None

    # 1) Profile page with 'Född' block
    profile_html = fetch_profile_html(session, horse_id)
    year = extract_birth_year_from_profile_html(profile_html or "")
    if year is not None:
        return year

    # 2) Printpedigree JSON
    pp_html = fetch_printpedigree_html(session, horse_id)
    year = extract_birth_year_from_dateofbirth_field(pp_html or "")
    if year is not None:
        return year

    # 3) No reliable birth-year data found
    return None
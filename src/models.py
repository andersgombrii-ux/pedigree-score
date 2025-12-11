from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Horse search & identification
# ---------------------------------------------------------------------------

@dataclass
class HorseSearchResult:
    """
    One row returned from the Travsport horse search API.

    This represents a *candidate* horse when you search by name.
    We will typically get several of these and then filter by birth_year
    (Född) or other criteria to pick the correct horse.
    """
    horse_id: str          # e.g. "ts501290"
    name: str              # e.g. "Moe Odin (NO)"
    birth_year: Optional[int] = None
    country: Optional[str] = None
    sex: Optional[str] = None          # e.g. "hingst", "sto"
    breed: Optional[str] = None        # e.g. "kallblodig travare"
    raw: Dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        """
        Short human-readable label useful for error messages and CLI output.
        """
        parts: List[str] = [self.name]
        if self.birth_year is not None:
            parts.append(str(self.birth_year))
        if self.country:
            parts.append(self.country)
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Pedigree representation
# ---------------------------------------------------------------------------

@dataclass
class PedigreeNode:
    """
    One ancestor in the 5-generation pedigree tree.

    This is intentionally generic and does not try to parse every piece of
    text. We only enforce:
      - a name
      - which generation/column (1..5) the node belongs to
      - optional registration / extra free-form text

    If we later need more structured fields (e.g. reg number, earnings),
    we can extend this dataclass without breaking other modules.
    """
    name: str
    generation: int                    # 1 = closest to root, 5 = furthest
    raw_text: str                      # full cell text as seen on page
    reg_no: Optional[str] = None       # e.g. "NK-970203"
    extra: Optional[str] = None        # any remaining free-form info


@dataclass
class PedigreeView:
    """
    A complete 5-generation pedigree layout for a single horse.

    This is the main object produced by the HTML parser and consumed
    by scoring / analysis code.
    """
    root_name: str                     # e.g. "Moe Odin (NO)"
    root_id: str                       # e.g. "ts501290"
    max_generations: int               # expected to be 5 for this project
    nodes: List[PedigreeNode]          # typically 62 nodes in 5-gen layout

    @property
    def ancestors_by_generation(self) -> Dict[int, List[PedigreeNode]]:
        """
        Convenience grouping: {generation: [nodes...]}.
        """
        by_gen: Dict[int, List[PedigreeNode]] = {}
        for node in self.nodes:
            by_gen.setdefault(node.generation, []).append(node)
        return by_gen
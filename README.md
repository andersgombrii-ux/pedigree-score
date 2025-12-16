Pedigree Score

A personal command-line Python project for exploring and analyzing horse pedigrees.

Overview

Pedigree Score is a CLI-based Python project that builds and analyzes a local pedigree database for horses.

It fetches pedigree data from an external source, parses it into structured trees, caches results locally, and incrementally merges multiple pedigree searches into a single ancestry graph. From this merged graph, the project can generate summaries, visualizations, and simple influence scores for ancestors across many generations.

This project is not production-ready. It was built as a learning exercise to practice working with non-trivial data structures and real-world data issues.

What This Project Does

Fetches horse pedigree data from an external source

Parses pedigrees into tree structures

Flattens and caches pedigrees locally

Merges multiple pedigrees into a growing ancestry graph

Analyzes ancestor structure and influence

Visualizes pedigrees directly in the terminal

Features
Pedigree Fetching & Parsing

Downloads printable pedigree pages

Parses ancestry into structured tree data

Local Cache & Merging

Stores flattened pedigrees locally

Builds a growing merged pedigree graph across runs

Ancestry Analysis

Generation summaries (unique vs repeated ancestors)

Deep ancestry support (10–20+ generations)

Ancestor Influence Scoring

Appearance-based ancestor counts

Multiple weighting models:

Linear decay

Exponential decay

Slow exponential decay

Power-law

ASCII Pedigree Output

Renders pedigree trees directly in the terminal

CLI-First Design

All functionality exposed through command-line flags

Installation
Clone the repository
git clone https://github.com/andersgombrii-ux/pedigree-score.git
cd pedigree-score

Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# or
.venv\Scripts\activate      # Windows

Install dependencies
pip install -r requirements.txt

Usage Examples
Fetch and inspect a pedigree
python -m src.main --name "Vårblomster" --year 2021

Run merged pedigree analysis
python -m src.main \
  --name "Vårblomster" \
  --year 2021 \
  --merged-summary

Control analysis depth
python -m src.main \
  --name "Vårblomster" \
  --year 2021 \
  --merged-summary \
  --appearance-max-depth 20 \
  --summary-max-depth 20

Render an ASCII pedigree
python -m src.main --name "Vårblomster" --year 2021 --ascii

Project Structure
src/
├── main.py                  # CLI entry point
├── travsport_api.py         # External data fetching
├── pedigree_parser.py       # HTML → pedigree tree parsing
├── lineage_utils.py         # Tree flattening utilities
├── pedigree_store.py        # Local pedigree cache
├── pedigree_graph.py        # Merged graph construction
├── pedigree_graph_store.py  # Graph persistence
├── pedigree_summary.py      # Generation summaries
├── pedigree_scoring.py      # Influence scoring
├── pedigree_ascii.py        # ASCII rendering
├── corrections.py           # Manual data corrections (limited)
└── age_gap.py               # Age gap diagnostics


The project is intentionally modular to support experimentation and refactoring.

Learning Goals

This project was used to practice:

CLI application design

Argument parsing, flags, and user feedback

Tree and graph data structures

Breadth-first traversal

Unique vs appearance-based ancestry

Caching and persistence

File-based caching

Incremental graph building

Working with imperfect data

Missing IDs

Conflicting metadata

Incomplete ancestry

Incremental development

Building features step by step

Refactoring as understanding improved

Known Issues & Limitations

This project intentionally accepts several limitations:

Incorrect or conflicting source data

Upstream pedigree data may be incomplete or inconsistent

Some horses have missing or conflicting identifiers or birth years

This is a known issue and not fully resolved

Incomplete ancestor resolution

Some ancestors exist but may be disconnected due to missing IDs

Performance

Focus is on clarity, not optimization

Very large merged graphs may become slow

Future Improvements

Possible future directions include:

Improved identity resolution across data sources

Better conflict handling and validation

Optional SQLite-based persistence

Performance optimizations for large graphs

Why I Built This

I wanted a non-trivial personal project that required:

Working with messy, real-world data

Implementing and traversing graph structures

Designing a CLI-based workflow rather than a web app

Horse pedigrees turned out to be a surprisingly effective problem domain for practicing these skills.

Project Status

This project is complete enough for Boot.dev submission and intentionally left open for future iteration and learning.
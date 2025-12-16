Pedigree Score

A personal Python project for exploring and analyzing horse pedigrees.

Project Overview

Pedigree Score is a command-line Python project that builds and analyzes a local pedigree database for horses.

The project fetches pedigree data from an external source, parses it into structured form, caches results locally, and incrementally merges multiple pedigree trees into a single ancestry graph. From this merged graph, the project can generate summaries, visualizations, and simple influence scores for ancestors across many generations.

This project was built as a learning exercise, not as a production system. The main goals were to practice:

Working with tree and graph data structures

Designing a CLI-driven Python application

Handling imperfect real-world data

Incremental development with caching and persistence

Features

Pedigree fetching & parsing

Fetches printable pedigree pages from an external site

Parses ancestry into structured tree data

Local pedigree cache

Stores flattened pedigrees locally to avoid repeated downloads

Builds a growing, merged pedigree graph across multiple runs

Merged ancestry analysis

Computes generation summaries (unique ancestors vs appearances)

Supports deep ancestry (10–20+ generations)

Ancestor influence scoring

Counts ancestor appearances

Multiple weighting schemes (linear, exponential, slow exponential, power-law)

ASCII pedigree visualization

Renders a text-based pedigree tree directly in the terminal

CLI-first workflow

All functionality is accessible via command-line options

Installation & Usage
Clone the repository
git clone https://github.com/<your-username>/pedigree-score.git
cd pedigree-score

Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# or
.venv\Scripts\activate      # Windows

Install dependencies
pip install -r requirements.txt

Basic usage

Fetch and analyze a pedigree:

python -m src.main --name "Vårblomster" --year 2021


Run merged pedigree summaries (across all cached pedigrees):

python -m src.main --name "Vårblomster" --year 2021 --merged-summary


Control depth of analysis:

python -m src.main \
  --name "Vårblomster" \
  --year 2021 \
  --merged-summary \
  --appearance-max-depth 20 \
  --summary-max-depth 20


Render an ASCII pedigree:

python -m src.main --name "Vårblomster" --year 2021 --ascii

Project Structure
src/
├── main.py                  # CLI entry point and orchestration
├── travsport_api.py         # External data fetching
├── pedigree_parser.py       # HTML → pedigree tree parsing
├── lineage_utils.py         # Tree flattening utilities
├── pedigree_store.py        # Local cache for flattened pedigrees
├── pedigree_graph.py        # Merged pedigree graph construction
├── pedigree_graph_store.py  # Persistence for merged graph
├── pedigree_summary.py      # Generation summaries
├── pedigree_scoring.py      # Ancestor influence scoring
├── pedigree_ascii.py        # ASCII tree rendering
├── corrections.py           # Manual data corrections (limited)
└── age_gap.py               # Age gap diagnostics


The project is intentionally modular to make it easier to experiment, refactor, and extend.

Learning Goals

This project helped me practice and reinforce:

CLI design

Argument parsing, flags, defaults, and user feedback

Tree and graph data structures

BFS traversal

Deduplicated vs appearance-based ancestry analysis

Caching and persistence

File-based caching

Incremental graph building across runs

Working with imperfect data

Missing IDs

Conflicting metadata

Incomplete ancestry

Incremental development

Building features step by step

Refactoring as understanding improved

Known Issues & Future Work

This project intentionally accepts several limitations:

Incorrect or conflicting source data

Upstream pedigree data may be incomplete or inconsistent

Some horses may have missing or conflicting birth years or identifiers

This is a known limitation and not fully resolved

Incomplete ancestor resolution

Some ancestors may exist as nodes but be disconnected due to missing identifiers

Performance

Current implementation prioritizes clarity over performance

Large merged graphs may become slow

Future improvements

More robust identity resolution

Better handling of conflicting data sources

Improved diagnostics and validation

Optional SQLite-based persistence

Why I Built This

I wanted a non-trivial project that forced me to work with:

Real-world messy data

Graph traversal logic

A CLI-based workflow instead of a web UI

Horse pedigrees turned out to be a surprisingly good domain for practicing these skills.
# Academic Literature Search

Academic Literature Search is a lightweight Python application for finding
papers across common academic sources from either the command line or a desktop
GUI.

It currently supports:

- PubMed through the official NCBI E-utilities API
- Google Scholar as a best-effort source for small ad hoc searches

The project is designed to stay easy to run on a fresh machine, so it uses only
the Python standard library.

## Why This Project

This project is useful when you want a small, transparent tool for literature
discovery without depending on a large framework or paid API. It is built for
quick exploratory searches, especially when you want to:

- enter one or more keywords or phrases
- search PubMed quickly from a desktop app or terminal
- export results into JSON for downstream analysis
- keep the code simple enough to modify for your own workflow

## Features

- Search with one or more keywords or phrases
- Combine terms with `AND`, `OR`, or simple spaces
- Choose one or more sources per search
- Browse results in a desktop interface
- Open the selected paper in a browser
- Export structured JSON or CSV results
- Reuse the same search engine from the CLI and the GUI

## Project Files

- `literature_search.py`: command-line interface and shared search logic
- `literature_search_gui.py`: Tkinter desktop application

## Requirements

- Python 3.10 or newer
- Internet access for PubMed and Google Scholar queries

No third-party packages are required.

## Installation

Clone the repository and run either the GUI or CLI directly:

```powershell
git clone https://github.com/LincolnGothic/academic-literature-search.git
cd .\academic-literature-search
python .\literature_search_gui.py
```

If you prefer the command line, you can run `literature_search.py` directly
without any extra setup.

## Quick Start

### Run the desktop app

```powershell
python .\literature_search_gui.py
```

### Run the command-line tool

```powershell
python .\literature_search.py cancer immunotherapy
python .\literature_search.py "graph neural networks" protein folding --source pubmed --max-results 5
python .\literature_search.py CRISPR --source pubmed --source scholar --format json --json-out .\results.json
python .\literature_search.py CRISPR --source pubmed --csv-out .\results.csv
```

### See all CLI options

```powershell
python .\literature_search.py --help
```

## Command-Line Examples

Search PubMed only:

```powershell
python .\literature_search.py "single-cell RNA-seq" --source pubmed --max-results 10
```

Combine multiple concepts with `OR`:

```powershell
python .\literature_search.py CRISPR Cas9 --operator or --source pubmed
```

Save machine-readable output:

```powershell
python .\literature_search.py cancer immunotherapy --format json --json-out .\results.json
python .\literature_search.py cancer immunotherapy --csv-out .\results.csv
```

Use environment variables for NCBI settings:

```powershell
$env:NCBI_EMAIL="you@example.com"
$env:NCBI_API_KEY="your_api_key"
python .\literature_search.py Alzheimer biomarker --source pubmed
```

## Desktop GUI

The GUI lets you:

- Enter one or more keywords or phrases, one per line or comma-separated
- Select PubMed, Google Scholar, or both
- Change result count, sort order, timeout, and optional NCBI settings
- Review results in a table
- Read abstracts and metadata in a detail pane
- Export the current search to JSON or CSV

The GUI is built with Tkinter, so it should run on standard Python
installations without extra dependencies.

## PubMed and Google Scholar Notes

- PubMed is the most reliable source for automation in this project.
- PubMed results include the abstract, PMID, journal, publication year, and
  author list when those fields are available from NCBI.
- Google Scholar does not offer a public bulk API and may return blocking
  responses such as HTTP 403 for automated requests.
- When Scholar blocks the request, the app reports the problem clearly instead
  of crashing.
- NCBI asks automated tools to identify themselves. The app sends a `tool`
  name automatically; use `--email`, set `NCBI_EMAIL`, and optionally set
  `NCBI_API_KEY` or pass `--ncbi-api-key`.
- NCBI's default E-utilities limit is 3 requests per second. With an API key,
  the limit is typically 10 requests per second.
- Google Scholar support should be treated as best-effort rather than guaranteed.

## Output

Each result can include:

- title
- full author list
- journal
- publication date
- publication year
- abstract
- PMID for PubMed results
- DOI when available
- source URL

JSON output is useful if you want to post-process results in Python, R, Excel,
or another analysis pipeline. CSV output is flattened for spreadsheet tools.

## Development Notes

- The CLI and GUI share the same search engine logic.
- PubMed integration uses the official NCBI E-utilities endpoints.
- The project intentionally avoids third-party dependencies to stay portable.

Run the local test suite with:

```powershell
python -m unittest discover -v
```

## Open Source License

This project is released under the MIT License. See [LICENSE](LICENSE).

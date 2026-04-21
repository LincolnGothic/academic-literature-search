# Academic Literature Search

Academic Literature Search is a lightweight Python application for finding
papers across common academic sources from either the command line or a desktop
GUI.

It currently supports:

- PubMed through the official NCBI E-utilities API
- Google Scholar as a best-effort source for small ad hoc searches

The project is designed to stay easy to run on a fresh machine, so it uses only
the Python standard library.

## Features

- Search with one or more keywords or phrases
- Combine terms with `AND`, `OR`, or simple spaces
- Choose one or more sources per search
- Browse results in a desktop interface
- Open the selected paper in a browser
- Export structured JSON results
- Reuse the same search engine from the CLI and the GUI

## Project Files

- `literature_search.py`: command-line interface and shared search logic
- `literature_search_gui.py`: Tkinter desktop application

## Requirements

- Python 3.10 or newer
- Internet access for PubMed and Google Scholar queries

No third-party packages are required.

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
```

### See all CLI options

```powershell
python .\literature_search.py --help
```

## Desktop GUI

The GUI lets you:

- Enter one or more keywords or phrases, one per line or comma-separated
- Select PubMed, Google Scholar, or both
- Change result count, sort order, timeout, and optional NCBI settings
- Review results in a table
- Read abstracts and metadata in a detail pane
- Export the current search to JSON

## PubMed and Google Scholar Notes

- PubMed is the most reliable source for automation in this project.
- Google Scholar does not offer a public bulk API and may return blocking
  responses such as HTTP 403 for automated requests.
- When Scholar blocks the request, the app reports the problem clearly instead
  of crashing.
- If you have an NCBI API key, you can provide it to improve PubMed rate limits.

## Open Source License

This project is released under the MIT License. See [LICENSE](LICENSE).

#!/bin/sh
set -eu

python3 -m pip install -r requirements-build.txt
pyinstaller --windowed --name "Academic Literature Search" literature_search_gui.py
pyinstaller --onefile --name literature-search literature_search.py

mkdir -p release
cp -R "dist/Academic Literature Search.app" release/
cp dist/literature-search release/
cp README.md LICENSE release/
ditto -c -k --sequesterRsrc --keepParent release dist/academic-literature-search-macos.zip

echo "Built dist/academic-literature-search-macos.zip"

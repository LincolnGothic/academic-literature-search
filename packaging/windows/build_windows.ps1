$ErrorActionPreference = "Stop"

python -m pip install -r requirements-build.txt
pyinstaller --onefile --windowed --name AcademicLiteratureSearch literature_search_gui.py
pyinstaller --onefile --name literature-search literature_search.py

New-Item -ItemType Directory -Force release | Out-Null
Copy-Item dist\AcademicLiteratureSearch.exe release\
Copy-Item dist\literature-search.exe release\
Copy-Item README.md,LICENSE release\
Compress-Archive -Path release\* -DestinationPath dist\academic-literature-search-windows.zip -Force

Write-Host "Built dist\academic-literature-search-windows.zip"

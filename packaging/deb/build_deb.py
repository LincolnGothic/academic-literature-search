#!/usr/bin/env python3
"""Build a Debian package for Academic Literature Search.

The package installs the Python source files, two command launchers, a desktop
entry, README, and license. It intentionally depends on system Python and
python3-tk instead of bundling a platform-specific Python runtime.
"""

from __future__ import annotations

import argparse
import gzip
import io
import tarfile
from pathlib import Path


PACKAGE_NAME = "academic-literature-search"
APP_DIR = "usr/share/academic-literature-search"
GUI_LAUNCHER = "usr/bin/academic-literature-search"
CLI_LAUNCHER = "usr/bin/literature-search"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def tar_bytes(entries: list[tuple[str, bytes | None, int, str]]) -> bytes:
    """Create a gzipped tar archive.

    Each entry is (path, content, mode, type), where type is "file" or "dir".
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for path, content, mode, entry_type in entries:
            info = tarfile.TarInfo(path)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            if entry_type == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                payload = content or b""
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))

    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as gz_file:
        gz_file.write(raw.getvalue())
    return compressed.getvalue()


def ar_member(name: str, content: bytes) -> bytes:
    encoded_name = (name + "/").encode("ascii")
    if len(encoded_name) > 16:
        raise ValueError(f"ar member name is too long: {name}")
    header = b"".join(
        [
            encoded_name.ljust(16, b" "),
            b"0".ljust(12, b" "),
            b"0".ljust(6, b" "),
            b"0".ljust(6, b" "),
            b"100644".ljust(8, b" "),
            str(len(content)).encode("ascii").ljust(10, b" "),
            b"`\n",
        ]
    )
    padding = b"\n" if len(content) % 2 else b""
    return header + content + padding


def write_ar_archive(path: Path, members: list[tuple[str, bytes]]) -> None:
    content = b"!<arch>\n" + b"".join(ar_member(name, data) for name, data in members)
    path.write_bytes(content)


def read_text_file(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def build_control_archive(version: str, installed_size_kb: int) -> bytes:
    control = f"""Package: {PACKAGE_NAME}
Version: {version}
Section: science
Priority: optional
Architecture: all
Maintainer: LincolnGothic <LincolnGothic@users.noreply.github.com>
Depends: python3, python3-tk, ca-certificates
Installed-Size: {installed_size_kb}
Homepage: https://github.com/LincolnGothic/academic-literature-search
Description: Desktop and CLI academic literature search tool
 Academic Literature Search is a lightweight Python application for searching
 academic literature from PubMed and optional best-effort Google Scholar lookup.
 It includes a Tkinter desktop interface, command-line workflow, and JSON/CSV
 export for downstream analysis.
"""
    return tar_bytes([("./control", control.encode("utf-8"), 0o644, "file")])


def build_data_archive(root: Path) -> bytes:
    gui_launcher = f"""#!/bin/sh
exec python3 /{APP_DIR}/literature_search_gui.py "$@"
""".encode("utf-8")
    cli_launcher = f"""#!/bin/sh
exec python3 /{APP_DIR}/literature_search.py "$@"
""".encode("utf-8")
    desktop_entry = f"""[Desktop Entry]
Type=Application
Name=Academic Literature Search
Comment=Search academic literature from PubMed
Exec=academic-literature-search
Terminal=false
Categories=Education;Science;
StartupNotify=true
""".encode("utf-8")

    entries: list[tuple[str, bytes | None, int, str]] = [
        ("./usr/", None, 0o755, "dir"),
        ("./usr/bin/", None, 0o755, "dir"),
        ("./usr/share/", None, 0o755, "dir"),
        (f"./{APP_DIR}/", None, 0o755, "dir"),
        ("./usr/share/applications/", None, 0o755, "dir"),
        (f"./{GUI_LAUNCHER}", gui_launcher, 0o755, "file"),
        (f"./{CLI_LAUNCHER}", cli_launcher, 0o755, "file"),
        (
            f"./usr/share/applications/{PACKAGE_NAME}.desktop",
            desktop_entry,
            0o644,
            "file",
        ),
    ]

    for filename in ["literature_search.py", "literature_search_gui.py", "README.md", "LICENSE"]:
        entries.append((f"./{APP_DIR}/{filename}", read_text_file(root / filename), 0o644, "file"))

    return tar_bytes(entries)


def build_deb(version: str, output_dir: Path) -> Path:
    root = repo_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    deb_path = output_dir / f"{PACKAGE_NAME}_{version}_all.deb"

    data_archive = build_data_archive(root)
    installed_size_kb = max(1, len(data_archive) // 1024)
    control_archive = build_control_archive(version, installed_size_kb)

    write_ar_archive(
        deb_path,
        [
            ("debian-binary", b"2.0\n"),
            ("control.tar.gz", control_archive),
            ("data.tar.gz", data_archive),
        ],
    )
    return deb_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Debian package.")
    parser.add_argument("--version", default="0.1.0", help="Package version. Default: 0.1.0")
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory where the .deb should be written. Default: dist",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deb_path = build_deb(args.version, repo_root() / args.output_dir)
    print(deb_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

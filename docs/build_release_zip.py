"""
Build the v0.7.0 release ZIP bundle.

Excludes: .venv, .git, .pytest_cache, __pycache__, .tmp, build artifacts.
Includes: code/, tests/, data/, docs/, plus standing files (README, etc).
"""

import os
import zipfile

# Project root (parent of code/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "docs", "z-pinch-postproc-v0.7.0.zip")

EXCLUDE_DIRS = {
    ".venv", ".git", ".pytest_cache", "__pycache__",
    "node_modules", ".tmp", "build", "dist", ".eggs",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo", ".whl", ".egg-info")
EXCLUDE_FILES = {
    "z-pinch-postproc-v0.7.0.zip",  # Don't include ourselves
}


def should_exclude_dir(d):
    return d in EXCLUDE_DIRS or d.startswith(".") and d not in {".github"}


def should_exclude_file(f):
    if f in EXCLUDE_FILES:
        return True
    return any(f.endswith(s) for s in EXCLUDE_FILE_SUFFIXES)


def build_zip():
    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(OUTPUT_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Filter out excluded dirs in-place to skip them in walk
            dirs[:] = sorted(d for d in dirs if not should_exclude_dir(d))
            for f in sorted(files):
                if should_exclude_file(f):
                    continue
                fp = os.path.join(root, f)
                arc = os.path.relpath(fp, PROJECT_ROOT)
                zf.write(fp, arc)
                file_count += 1
                total_bytes += os.path.getsize(fp)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  Files: {file_count}")
    print(f"  Total uncompressed: {total_bytes / 1024:.1f} KB")
    print(f"  Compressed size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    build_zip()
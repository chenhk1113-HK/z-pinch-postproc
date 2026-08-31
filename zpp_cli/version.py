"""zpp version CLI."""
import sys


def main() -> int:
    """Print zpp version + key paths."""
    try:
        from zpp._version import __version__, __git_sha__, __build_date__
        sha_short = __git_sha__[:7] if __git_sha__ else "unknown"
        print(f"zpp {__version__} (git: {sha_short}, built: {__build_date__})")
    except ImportError:
        # Fall back to VERSION file
        from pathlib import Path
        vfile = Path(__file__).parent.parent / "VERSION"
        version = vfile.read_text().strip() if vfile.exists() else "unknown"
        print(f"zpp {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
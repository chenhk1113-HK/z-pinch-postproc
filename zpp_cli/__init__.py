"""zpp CLI — minimal console entry points.

After `pip install -e .`:
    zpp-tbr           # run a parametric TBR sweep
    zpp-version       # print version + paths

These are thin wrappers around the public API in `code/zpp_tbr.py`.
"""
from .version import main as version_main
from .tbr import main as tbr_main

__all__ = ["version_main", "tbr_main"]
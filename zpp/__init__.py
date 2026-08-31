"""zpp core physics package — Tier 1-17 modules.

This is intentionally flat (no nested subpackages other than
`adapters/`) so that all the core physics modules can be imported as
`zpp_*` whether you're using `pip install -e .` (which exposes
`zpp.zpp_*` imports) or the legacy `sys.path.insert("code")` approach
which exposes them as `zpp_*` directly.

Subpackage layout:
  code/                   # this package (flat, ~29 modules)
  code/adapters/          # external wrappers (8 modules)
"""
"""Adapter modules — wrappers around external upstream codes.

This subpackage contains adapters for:
  - OpenMC (real_openmc_adapter, subprocess_adapters)
  - PROCESS (real_process_adapter)
  - Paramak (real_paramak_adapter)
  - FISPACT-II (fispact_adapter)
  - Antong Fusion references (zffr_references)
  - Abstract adapter interfaces (adapters)

Adapters are NOT in the core physics path — they wrap external tools
and may require extra dependencies. Tier 6+ TBR sweeps do not depend
on any of these; they use the parametric formula or the
zpp_real_openmc_transport wrapper (a Tier 8.A core module, NOT an
adapter).

Module organization:
  code/zpp_*.py            # core physics (always importable)
  code/adapters/zpp_*.py   # external wrappers (may have heavy deps)
"""
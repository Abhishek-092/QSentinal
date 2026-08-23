import pytest
from qds.protocol import run_session, SessionConfig


def test_import_boundary_purity():
    """Verify that qds module has zero imports from qsentinel_monitor, api, attacks, or experiments."""
    import sys
    import qds.bell_pair
    import qds.pauli
    import qds.teleportation
    import qds.measurement
    import qds.noise
    import qds.transcript
    import qds.protocol

    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("qds."):
            mod = sys.modules[mod_name]
            if hasattr(mod, "__file__") and mod.__file__:
                with open(mod.__file__, "r", encoding="utf-8") as f:
                    content = f.read()
                    for forbidden in ["qsentinel_monitor", "api", "attacks", "experiments", "frontend"]:
                        assert forbidden not in content, f"Forbidden import '{forbidden}' found in {mod_name}"

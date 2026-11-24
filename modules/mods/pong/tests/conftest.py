"""The pong mod's tests: load the package through the §7 loader.

The tests import ``botforge.mods.pong.*`` — the same name the runtime
uses (the loader registers the core package); no sys.path tricks, one
import name everywhere.
"""

from __future__ import annotations


def pytest_configure() -> None:
    from botforge.core.services.mod_entrypoint import load_mod_package
    from botforge.core.services.mod_layout import default_repo_root

    load_mod_package("pong", default_repo_root())

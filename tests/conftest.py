import os
import sys
import pytest

def pytest_sessionfinish(session, exitstatus):
    session.config._chess_vision_exitstatus = exitstatus


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # PySide6 puede abortar al destruir objetos C++ en Windows; esperar al resumen de pytest.
    status = getattr(config, "_chess_vision_exitstatus", None)
    if sys.platform == "win32" and status is not None:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(status))

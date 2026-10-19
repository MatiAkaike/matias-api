"""Las pruebas de política del chat no prueban el antibots: lo desactivan. Las de antibots y acceso sí lo usan."""
import pytest

import anti_bots

_CON_ANTIBOTS = {"test_anti_bots", "test_presentacion_acceso"}


@pytest.fixture(autouse=True)
def _sin_antibots(request, monkeypatch):
    if request.module.__name__ in _CON_ANTIBOTS:
        return
    monkeypatch.setattr(anti_bots, "origen_valido", lambda *a, **k: True)
    monkeypatch.setattr(anti_bots, "verificar", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(anti_bots, "hay_cupo_global", lambda: True)

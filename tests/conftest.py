"""
Configuración de los tests de integración.

Los tests usan la API real contra un MongoDB real (el del docker compose), pero
en una base aparte, `gym_test`, que se vuelve a cargar antes de cada test.
La base `gym` con la que trabajás no se toca.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
os.environ["MONGO_DB"] = "gym_test"  # antes de importar la app, que lee la config al importarse
sys.path.insert(0, str(RAIZ / "api"))
sys.path.insert(0, str(RAIZ / "scripts"))

import seed  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db():
    base = get_db()
    assert base.name == "gym_test"
    seed.cargar(base)
    yield base


@pytest.fixture
def api(db):
    # raise_server_exceptions=False: un error interno vuelve como respuesta 500 en vez de cortar el test
    return TestClient(app, raise_server_exceptions=False)


def ahora():
    return datetime.now(timezone.utc)


@pytest.fixture
def buscar_cliente(db):
    """Devuelve un cliente que cumpla una condición, para no depender de IDs fijos."""
    def _buscar(**condiciones):
        m = ahora()
        filtros = {
            "vigente": {"plan_actual.fecha_vencimiento": {"$gt": m}, "estado": "activo"},
            "vencido": {"plan_actual.fecha_vencimiento": {"$lt": m}, "estado": "activo"},
            "sin_plan": {"plan_actual": {"$exists": False}, "estado": "activo"},
            "inactivo": {"estado": "inactivo"},
        }
        filtro = dict(filtros[condiciones.pop("tipo", "vigente")])
        filtro.update(condiciones)
        cliente = db.clientes.find_one(filtro)
        assert cliente is not None, f"No hay datos de prueba para {filtro}"
        return cliente
    return _buscar

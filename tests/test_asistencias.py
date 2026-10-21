"""
Tests del caso de consistencia: registrar una asistencia descuenta un cupo,
y si algo falla no queda nada a medias.
"""

from concurrent.futures import ThreadPoolExecutor

from app.errores import Conflicto
from app.repositories.asistencias import AsistenciasRepository
from app.schemas import AsistenciaCrear
from app.services.asistencias import AsistenciasService


def estado(db, cliente_id):
    cliente = db.clientes.find_one({"_id": cliente_id})
    return cliente["plan_actual"]["cupos_restantes"], db.asistencias.count_documents({"cliente_id": cliente_id})


def registrar(api, cliente, actividad="musculacion"):
    return api.post("/asistencias", json={"cliente_id": str(cliente["_id"]), "actividad": actividad})


def test_registrar_descuenta_un_cupo(api, db, buscar_cliente):
    cliente = buscar_cliente(**{"plan_actual.cupos_restantes": {"$gte": 2}})
    cupos, asistencias = estado(db, cliente["_id"])

    respuesta = registrar(api, cliente)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["cupos_restantes_post"] == cupos - 1
    assert estado(db, cliente["_id"]) == (cupos - 1, asistencias + 1)


def test_sin_cupos_da_409_y_no_cambia_nada(api, db, buscar_cliente):
    cliente = buscar_cliente(**{"plan_actual.cupos_restantes": 0})
    antes = estado(db, cliente["_id"])
    respuesta = registrar(api, cliente)
    assert respuesta.status_code == 409
    assert "cupos" in respuesta.json()["detalle"]
    assert estado(db, cliente["_id"]) == antes


def test_plan_vencido_da_409(api, db, buscar_cliente):
    cliente = buscar_cliente(tipo="vencido", **{"plan_actual.cupos_restantes": {"$gt": 0}})
    antes = estado(db, cliente["_id"])
    respuesta = registrar(api, cliente)
    assert respuesta.status_code == 409
    assert "vencido" in respuesta.json()["detalle"]
    assert estado(db, cliente["_id"]) == antes


def test_cliente_sin_plan_da_409(api, buscar_cliente):
    assert registrar(api, buscar_cliente(tipo="sin_plan")).status_code == 409


def test_cliente_inexistente_da_404(api):
    respuesta = api.post("/asistencias", json={"cliente_id": "6710a1b2c3d4e5f6a7b8c9d0", "actividad": "crossfit"})
    assert respuesta.status_code == 404


def test_actividad_no_incluida_da_422(api, db, buscar_cliente):
    cliente = buscar_cliente(**{"plan_actual.nombre": "8 clases", "plan_actual.cupos_restantes": {"$gt": 0}})
    antes = estado(db, cliente["_id"])
    assert registrar(api, cliente, actividad="hyrox").status_code == 422  # el plan de 8 no incluye hyrox
    assert estado(db, cliente["_id"]) == antes


def test_plan_libre_no_descuenta(api, db, buscar_cliente):
    cliente = buscar_cliente(**{"plan_actual.nombre": "Libre"})
    asistencias_antes = db.asistencias.count_documents({"cliente_id": cliente["_id"]})
    respuesta = registrar(api, cliente)
    assert respuesta.status_code == 201
    assert respuesta.json()["cupos_restantes_post"] is None
    assert estado(db, cliente["_id"]) == (None, asistencias_antes + 1)


def test_falla_en_medio_de_la_transaccion_no_deja_nada_a_medias(api, db, buscar_cliente, monkeypatch):
    """
    Simula que el insert de la asistencia falla DESPUÉS de haber descontado el cupo
    (por ejemplo, se cae la conexión). La transacción tiene que deshacer el descuento.
    """
    cliente = buscar_cliente(**{"plan_actual.cupos_restantes": {"$gte": 2}})
    antes = estado(db, cliente["_id"])

    def insert_que_falla(self, documento, session=None):
        raise RuntimeError("se cortó la conexión")

    monkeypatch.setattr(AsistenciasRepository, "insertar", insert_que_falla)
    respuesta = registrar(api, cliente)

    assert respuesta.status_code == 500
    assert estado(db, cliente["_id"]) == antes  # el cupo NO quedó descontado


def test_registros_simultaneos_del_ultimo_cupo(db, buscar_cliente):
    """
    Prueba de concurrencia: 5 recepcionistas registran al mismo cliente, al que le
    queda 1 solo cupo, exactamente al mismo tiempo. Solo uno puede tener éxito.
    """
    cliente = buscar_cliente(**{"plan_actual.cupos_restantes": {"$gte": 1}, "plan_actual.nombre": "12 clases"})
    db.clientes.update_one({"_id": cliente["_id"]}, {"$set": {"plan_actual.cupos_restantes": 1}})
    _, asistencias_antes = estado(db, cliente["_id"])
    servicio = AsistenciasService(db)
    datos = AsistenciaCrear(cliente_id=str(cliente["_id"]), actividad="crossfit")

    def intentar(_):
        try:
            servicio.registrar(datos)
            return "ok"
        except Conflicto:
            return "sin cupos"

    with ThreadPoolExecutor(max_workers=5) as pool:
        resultados = list(pool.map(intentar, range(5)))

    assert resultados.count("ok") == 1
    assert resultados.count("sin cupos") == 4
    assert estado(db, cliente["_id"]) == (0, asistencias_antes + 1)

"""
Primera prueba del caso de consistencia: registrar una asistencia y descontar un cupo.

Uso:
    python scripts/prueba_transaccion.py

La operación toca dos documentos de dos colecciones:
  1. clientes:    plan_actual.cupos_restantes - 1
  2. asistencias: se inserta la asistencia nueva

Si la 1 se completa y la 2 falla, el cliente pierde un cupo sin haber entrenado.
Si fuera al revés, entrena gratis. Por eso las dos van dentro de una transacción:
o se guardan las dos, o ninguna.

El descuento además tiene la condición "cupos_restantes > 0 y plan no vencido"
dentro del mismo update, así que dos recepcionistas registrando al mismo cliente
a la vez nunca pueden dejarlo en -1 (el update es atómico sobre el documento).

En la semana 3 esta función pasa a la capa de repositorios de la API.

Al final, volver a correr `python scripts/seed.py` deja los datos como al principio.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"))
db = client[os.getenv("MONGO_DB", "gym")]


class AsistenciaRechazada(Exception):
    pass


class FallaSimulada(Exception):
    pass


def registrar_asistencia(cliente_id, actividad, simular_falla=False):
    """Registra la asistencia y descuenta el cupo en una única transacción."""

    def operacion(session):
        ahora = datetime.now(timezone.utc)
        cliente = db.clientes.find_one({"_id": cliente_id}, session=session)
        if cliente is None:
            raise AsistenciaRechazada("el cliente no existe")
        plan = cliente.get("plan_actual")
        if plan is None:
            raise AsistenciaRechazada("el cliente no tiene plan")

        filtro = {"_id": cliente_id, "estado": "activo", "plan_actual.fecha_vencimiento": {"$gt": ahora}}
        if plan["cupos_totales"] is None:
            # Plan libre: no hay cupos que descontar, solo se valida que esté vigente
            actualizado = db.clientes.find_one(filtro, session=session)
        else:
            filtro["plan_actual.cupos_restantes"] = {"$gt": 0}
            actualizado = db.clientes.find_one_and_update(
                filtro,
                {"$inc": {"plan_actual.cupos_restantes": -1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
        if actualizado is None:
            raise AsistenciaRechazada("sin cupos, plan vencido o cliente no activo")

        if simular_falla:
            # Simula que se corta la conexión o se cae la API entre el update y el insert
            raise FallaSimulada("error después de descontar el cupo")

        asistencia = {"cliente_id": cliente_id, "fecha_hora": ahora, "actividad": actividad}
        restantes = actualizado["plan_actual"]["cupos_restantes"]
        if restantes is not None:
            asistencia["cupos_restantes_post"] = restantes
        db.asistencias.insert_one(asistencia, session=session)
        return restantes

    with client.start_session() as session:
        # with_transaction hace commit si la función termina bien y abort si lanza una excepción
        return session.with_transaction(operacion)


def estado(cliente_id):
    c = db.clientes.find_one({"_id": cliente_id})
    return c["plan_actual"]["cupos_restantes"], db.asistencias.count_documents({"cliente_id": cliente_id})


def probar(titulo, cliente, esperado_ok, **kwargs):
    print(f"\n--- {titulo} ---")
    print(f"Cliente: {cliente['nombre']} {cliente['apellido']} ({cliente['plan_actual']['nombre']})")
    cupos_antes, asist_antes = estado(cliente["_id"])
    print(f"Antes:   cupos = {cupos_antes}, asistencias = {asist_antes}")
    try:
        registrar_asistencia(cliente["_id"], "crossfit", **kwargs)
        resultado = "registrada"
    except (AsistenciaRechazada, FallaSimulada) as e:
        resultado = f"rechazada ({e})"
    cupos_despues, asist_despues = estado(cliente["_id"])
    print(f"Después: cupos = {cupos_despues}, asistencias = {asist_despues} -> {resultado}")

    if esperado_ok:
        ok = cupos_despues == cupos_antes - 1 and asist_despues == asist_antes + 1
    else:
        ok = cupos_despues == cupos_antes and asist_despues == asist_antes
    print("RESULTADO: OK" if ok else "RESULTADO: ERROR, la base quedó inconsistente")
    return ok


def demo_sin_transaccion(cliente):
    """Muestra el problema: sin transacción, el update queda aplicado aunque el insert falle."""
    print("\n--- Sin transacción: falla después de descontar el cupo ---")
    cupos_antes, asist_antes = estado(cliente["_id"])
    print(f"Antes:   cupos = {cupos_antes}, asistencias = {asist_antes}")
    db.clientes.update_one({"_id": cliente["_id"]}, {"$inc": {"plan_actual.cupos_restantes": -1}})
    # ... acá se cae el proceso y el insert de la asistencia nunca llega a ejecutarse
    cupos_despues, asist_despues = estado(cliente["_id"])
    print(f"Después: cupos = {cupos_despues}, asistencias = {asist_despues}")
    print("RESULTADO: el cliente perdió un cupo sin asistencia registrada (inconsistencia)")
    # Se revierte a mano para no dejar la base rota
    db.clientes.update_one({"_id": cliente["_id"]}, {"$inc": {"plan_actual.cupos_restantes": 1}})
    print("(cambio revertido)")


def main():
    ahora = datetime.now(timezone.utc)
    vigente = {"estado": "activo", "plan_actual.fecha_vencimiento": {"$gt": ahora}}
    con_cupos = db.clientes.find_one({**vigente, "plan_actual.cupos_restantes": {"$gte": 3}})
    sin_cupos = db.clientes.find_one({**vigente, "plan_actual.cupos_restantes": 0})
    vencido = db.clientes.find_one({"estado": "activo", "plan_actual.fecha_vencimiento": {"$lt": ahora},
                                    "plan_actual.cupos_restantes": {"$gt": 0}})

    resultados = [
        probar("1. Caso normal: cliente con cupos", con_cupos, esperado_ok=True),
        probar("2. Cliente sin cupos", sin_cupos, esperado_ok=False),
        probar("3. Cliente con plan vencido (aunque le quedan cupos)", vencido, esperado_ok=False),
        probar("4. Con transacción: falla después de descontar el cupo", con_cupos,
               esperado_ok=False, simular_falla=True),
    ]
    demo_sin_transaccion(con_cupos)

    print(f"\n{sum(resultados)}/{len(resultados)} pruebas OK")


if __name__ == "__main__":
    main()

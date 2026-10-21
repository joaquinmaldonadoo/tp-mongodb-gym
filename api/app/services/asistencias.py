"""
Registro de asistencias: el caso de consistencia del TP.

Registrar una asistencia toca dos documentos de dos colecciones:
  1. clientes:    plan_actual.cupos_restantes - 1
  2. asistencias: se inserta la asistencia

Si la 1 se guarda y la 2 falla, el cliente pierde un cupo sin haber entrenado.
Si fuera al revés, entrena gratis. Por eso las dos van en una transacción
multidocumento: o se guardan las dos, o ninguna.
"""

from pymongo.database import Database

from ..db import ahora, en_transaccion
from ..errores import Conflicto, NoEncontrado, ReglaDeNegocio
from ..repositories.asistencias import AsistenciasRepository
from ..repositories.base import a_object_id
from ..repositories.clientes import ClientesRepository
from ..repositories.planes import PlanesRepository
from ..schemas import AsistenciaCrear


class AsistenciasService:
    def __init__(self, db: Database):
        self.db = db
        self.clientes = ClientesRepository(db)
        self.planes = PlanesRepository(db)
        self.asistencias = AsistenciasRepository(db)

    def registrar(self, datos: AsistenciaCrear) -> dict:
        cliente_id = a_object_id(datos.cliente_id, "ID de cliente")

        def operacion(session):
            momento = ahora()

            # 1. Validaciones con mensajes claros para recepción
            cliente = self.clientes.obtener(cliente_id, session=session)
            if cliente is None:
                raise NoEncontrado(f"No existe un cliente con ID {datos.cliente_id}")
            if cliente["estado"] != "activo":
                raise Conflicto(f"El cliente está {cliente['estado']}")
            plan = cliente.get("plan_actual")
            if plan is None:
                raise Conflicto("El cliente no tiene un plan asignado")
            if plan["fecha_vencimiento"] <= momento:
                raise Conflicto("El plan del cliente está vencido")

            plan_catalogo = self.planes.obtener(plan["plan_id"], session=session)
            if plan_catalogo and datos.actividad not in plan_catalogo["actividades_incluidas"]:
                incluidas = ", ".join(plan_catalogo["actividades_incluidas"])
                raise ReglaDeNegocio(f"'{datos.actividad}' no está incluida en el plan {plan['nombre']} ({incluidas})")

            # 2. Descuento del cupo. El filtro vuelve a chequear las condiciones en el
            #    mismo update atómico, por si otra operación cambió el cliente recién.
            if plan["cupos_totales"] is None:
                actualizado = self.clientes.obtener_si_vigente(cliente_id, momento, session)
            else:
                actualizado = self.clientes.descontar_cupo(cliente_id, momento, session)
            if actualizado is None:
                raise Conflicto("El cliente no tiene cupos disponibles")

            # 3. Inserción de la asistencia, dentro de la misma transacción
            asistencia = {"cliente_id": cliente_id, "fecha_hora": momento, "actividad": datos.actividad}
            if datos.coach:
                asistencia["coach"] = datos.coach
            restantes = actualizado["plan_actual"]["cupos_restantes"]
            if restantes is not None:
                asistencia["cupos_restantes_post"] = restantes
            return self.asistencias.insertar(asistencia, session=session)

        # Si cualquier paso lanza una excepción, la transacción se aborta y no queda nada a medias
        return en_transaccion(self.db, operacion)

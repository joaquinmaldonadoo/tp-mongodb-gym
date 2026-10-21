"""
Lógica de negocio de clientes: arma los filtros, aplica las reglas (qué se puede
modificar, qué planes se pueden asignar) y traduce los errores de Mongo a
errores del dominio. Usa los repositorios para leer y escribir.
"""

import re
from datetime import timedelta
from typing import List, Optional, Tuple

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..db import ahora, en_transaccion
from ..errores import Conflicto, NoEncontrado, ReglaDeNegocio
from ..repositories.asistencias import AsistenciasRepository
from ..repositories.base import a_object_id
from ..repositories.clientes import ClientesRepository
from ..repositories.planes import PlanesRepository
from ..schemas import ClienteActualizar, ClienteCrear

MENSAJE_DNI_REPETIDO = "Ya existe un cliente con ese DNI"


class ClientesService:
    def __init__(self, db: Database):
        self.db = db
        self.clientes = ClientesRepository(db)
        self.planes = PlanesRepository(db)
        self.asistencias = AsistenciasRepository(db)

    # --- CRUD ----------------------------------------------------------------

    def crear(self, datos: ClienteCrear) -> dict:
        documento = datos.model_dump(exclude_none=True)
        documento["fecha_alta"] = ahora()
        try:
            return self.clientes.crear(documento)
        except DuplicateKeyError:
            raise Conflicto(MENSAJE_DNI_REPETIDO)

    def obtener(self, cliente_id: str) -> dict:
        cliente = self.clientes.obtener(a_object_id(cliente_id, "ID de cliente"))
        if cliente is None:
            raise NoEncontrado(f"No existe un cliente con ID {cliente_id}")
        return cliente

    def listar(self, estado: Optional[str] = None, plan: Optional[str] = None,
               cupos_max: Optional[int] = None, vigente: Optional[bool] = None,
               buscar: Optional[str] = None, limite: int = 20, salto: int = 0) -> Tuple[int, List[dict]]:
        filtro = {}
        if estado:
            filtro["estado"] = estado
        if plan:
            filtro["plan_actual.nombre"] = plan
        if cupos_max is not None:
            filtro["plan_actual.cupos_restantes"] = {"$lte": cupos_max}
        if vigente is not None:
            momento = ahora()
            filtro["plan_actual.fecha_vencimiento"] = {"$gt": momento} if vigente else {"$lte": momento}
        if buscar:
            # Busca por nombre, apellido o DNI sin distinguir mayúsculas.
            # re.escape evita que caracteres como "." o "*" se interpreten como regex.
            patron = {"$regex": re.escape(buscar), "$options": "i"}
            filtro["$or"] = [{"nombre": patron}, {"apellido": patron}, {"dni": patron}]
        return self.clientes.listar(filtro, limite, salto)

    def actualizar(self, cliente_id: str, cambios: ClienteActualizar) -> dict:
        oid = a_object_id(cliente_id, "ID de cliente")
        enviados = cambios.model_dump(exclude_unset=True)
        asignar = {k: v for k, v in enviados.items() if v is not None}
        borrar = [k for k, v in enviados.items() if v is None]  # null en un opcional = borrarlo
        try:
            actualizado = self.clientes.actualizar(oid, asignar, borrar)
        except DuplicateKeyError:
            raise Conflicto(MENSAJE_DNI_REPETIDO)
        if actualizado is None:
            raise NoEncontrado(f"No existe un cliente con ID {cliente_id}")
        return actualizado

    def eliminar(self, cliente_id: str) -> int:
        """
        Borra el cliente y todo su historial de asistencias en una transacción.
        Sin transacción, un corte a la mitad podría dejar asistencias que apuntan
        a un cliente que ya no existe. Devuelve cuántas asistencias se borraron.
        """
        oid = a_object_id(cliente_id, "ID de cliente")

        def operacion(session):
            if not self.clientes.eliminar(oid, session=session):
                raise NoEncontrado(f"No existe un cliente con ID {cliente_id}")
            return self.asistencias.eliminar_de_cliente(oid, session=session)

        return en_transaccion(self.db, operacion)

    # --- Plan e historial ----------------------------------------------------

    def asignar_plan(self, cliente_id: str, plan_id: str) -> dict:
        """
        Asigna o renueva el plan (RF2). Se embebe una COPIA del plan con el precio
        y los cupos de hoy: si mañana el gimnasio cambia el precio, lo que el
        cliente ya pagó no cambia. Un plan nuevo reemplaza al anterior y el
        período arranca en este momento.
        """
        oid_cliente = a_object_id(cliente_id, "ID de cliente")
        plan = self.planes.obtener(a_object_id(plan_id, "ID de plan"))
        if plan is None:
            raise NoEncontrado(f"No existe un plan con ID {plan_id}")
        if not plan["activo"]:
            raise ReglaDeNegocio(f"El plan '{plan['nombre']}' está discontinuado y no se puede asignar")

        cliente = self.clientes.obtener(oid_cliente)
        if cliente is None:
            raise NoEncontrado(f"No existe un cliente con ID {cliente_id}")
        if cliente["estado"] != "activo":
            raise Conflicto(f"El cliente está {cliente['estado']}: hay que reactivarlo antes de asignarle un plan")

        inicio = ahora()
        cupos = plan.get("cupos_mensuales")  # None en el plan libre
        plan_actual = {
            "plan_id": plan["_id"],
            "nombre": plan["nombre"],
            "precio_pagado": plan["precio"],
            "cupos_totales": cupos,
            "cupos_restantes": cupos,
            "fecha_inicio": inicio,
            "fecha_vencimiento": inicio + timedelta(days=plan["duracion_dias"]),
        }
        return self.clientes.asignar_plan(oid_cliente, plan_actual)

    def historial(self, cliente_id: str, limite: int) -> List[dict]:
        cliente = self.obtener(cliente_id)
        return self.asistencias.historial(cliente["_id"], limite)

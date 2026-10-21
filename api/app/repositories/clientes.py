"""
Repositorio de clientes: es la única parte de la aplicación que habla con la
colección `clientes`. No conoce HTTP ni reglas de negocio, solo cómo leer y
escribir documentos.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database


class ClientesRepository:
    def __init__(self, db: Database):
        self.coleccion = db.clientes

    def crear(self, documento: dict) -> dict:
        resultado = self.coleccion.insert_one(documento)
        documento["_id"] = resultado.inserted_id
        return documento

    def obtener(self, cliente_id: ObjectId, session: Optional[ClientSession] = None) -> Optional[dict]:
        return self.coleccion.find_one({"_id": cliente_id}, session=session)

    def listar(self, filtro: dict, limite: int, salto: int) -> Tuple[int, List[dict]]:
        total = self.coleccion.count_documents(filtro)
        cursor = (self.coleccion.find(filtro)
                  .sort([("apellido", ASCENDING), ("nombre", ASCENDING)])
                  .skip(salto)
                  .limit(limite))
        return total, list(cursor)

    def actualizar(self, cliente_id: ObjectId, asignar: dict, borrar: List[str]) -> Optional[dict]:
        cambios = {}
        if asignar:
            cambios["$set"] = asignar
        if borrar:
            cambios["$unset"] = {campo: "" for campo in borrar}
        return self.coleccion.find_one_and_update(
            {"_id": cliente_id}, cambios, return_document=ReturnDocument.AFTER)

    def asignar_plan(self, cliente_id: ObjectId, plan_actual: dict) -> Optional[dict]:
        return self.coleccion.find_one_and_update(
            {"_id": cliente_id}, {"$set": {"plan_actual": plan_actual}}, return_document=ReturnDocument.AFTER)

    def eliminar(self, cliente_id: ObjectId, session: Optional[ClientSession] = None) -> bool:
        return self.coleccion.delete_one({"_id": cliente_id}, session=session).deleted_count == 1

    def descontar_cupo(self, cliente_id: ObjectId, ahora: datetime, session: ClientSession) -> Optional[dict]:
        """
        Resta un cupo SOLO si el cliente está activo, el plan está vigente y le
        quedan cupos. La condición y el descuento van en la misma operación, que
        es atómica sobre el documento: dos registros simultáneos nunca pueden
        dejar los cupos en -1. Devuelve el cliente actualizado o None si no se cumplió.
        """
        return self.coleccion.find_one_and_update(
            {
                "_id": cliente_id,
                "estado": "activo",
                "plan_actual.fecha_vencimiento": {"$gt": ahora},
                "plan_actual.cupos_restantes": {"$gt": 0},
            },
            {"$inc": {"plan_actual.cupos_restantes": -1}},
            return_document=ReturnDocument.AFTER,
            session=session,
        )

    def obtener_si_vigente(self, cliente_id: ObjectId, ahora: datetime, session: ClientSession) -> Optional[dict]:
        """Para el plan libre: no hay cupos que descontar, solo se confirma que esté vigente."""
        return self.coleccion.find_one(
            {"_id": cliente_id, "estado": "activo", "plan_actual.fecha_vencimiento": {"$gt": ahora}},
            session=session,
        )

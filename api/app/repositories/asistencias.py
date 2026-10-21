"""Repositorio de asistencias."""

from typing import List, Optional

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.client_session import ClientSession
from pymongo.database import Database


class AsistenciasRepository:
    def __init__(self, db: Database):
        self.coleccion = db.asistencias

    def insertar(self, documento: dict, session: Optional[ClientSession] = None) -> dict:
        resultado = self.coleccion.insert_one(documento, session=session)
        documento["_id"] = resultado.inserted_id
        return documento

    def historial(self, cliente_id: ObjectId, limite: int) -> List[dict]:
        # Usa el índice compuesto cliente_fecha { cliente_id: 1, fecha_hora: -1 }:
        # filtra por cliente y ya devuelve ordenado, sin ordenar en memoria
        return list(self.coleccion.find({"cliente_id": cliente_id})
                    .sort("fecha_hora", DESCENDING)
                    .limit(limite))

    def eliminar_de_cliente(self, cliente_id: ObjectId, session: Optional[ClientSession] = None) -> int:
        return self.coleccion.delete_many({"cliente_id": cliente_id}, session=session).deleted_count

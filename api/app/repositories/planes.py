"""Repositorio de planes (catálogo). La API solo lo lee."""

from typing import List, Optional

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.client_session import ClientSession
from pymongo.database import Database


class PlanesRepository:
    def __init__(self, db: Database):
        self.coleccion = db.planes

    def listar(self, solo_activos: bool) -> List[dict]:
        filtro = {"activo": True} if solo_activos else {}
        return list(self.coleccion.find(filtro).sort("precio", ASCENDING))

    def obtener(self, plan_id: ObjectId, session: Optional[ClientSession] = None) -> Optional[dict]:
        return self.coleccion.find_one({"_id": plan_id}, session=session)

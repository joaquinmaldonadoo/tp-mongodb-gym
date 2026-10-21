"""Consulta del catálogo de planes."""

from typing import List

from pymongo.database import Database

from ..errores import NoEncontrado
from ..repositories.base import a_object_id
from ..repositories.planes import PlanesRepository


class PlanesService:
    def __init__(self, db: Database):
        self.planes = PlanesRepository(db)

    def listar(self, solo_activos: bool) -> List[dict]:
        return self.planes.listar(solo_activos)

    def obtener(self, plan_id: str) -> dict:
        plan = self.planes.obtener(a_object_id(plan_id, "ID de plan"))
        if plan is None:
            raise NoEncontrado(f"No existe un plan con ID {plan_id}")
        return plan

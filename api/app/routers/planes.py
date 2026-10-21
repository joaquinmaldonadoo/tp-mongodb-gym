"""Consulta del catálogo de planes (para saber qué plan_id asignar)."""

from typing import List

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from ..db import get_db
from ..repositories.base import a_salida
from ..schemas import PlanSalida
from ..services.planes import PlanesService

router = APIRouter(prefix="/planes", tags=["Planes"])


def servicio(db: Database = Depends(get_db)) -> PlanesService:
    return PlanesService(db)


@router.get("", response_model=List[PlanSalida], summary="Listar planes")
def listar_planes(solo_activos: bool = Query(True, description="false incluye los discontinuados"),
                  svc: PlanesService = Depends(servicio)):
    return [a_salida(p) for p in svc.listar(solo_activos)]


@router.get("/{plan_id}", response_model=PlanSalida, summary="Obtener un plan por ID",
            responses={400: {"description": "ID mal formado"}, 404: {"description": "El plan no existe"}})
def obtener_plan(plan_id: str, svc: PlanesService = Depends(servicio)):
    return a_salida(svc.obtener(plan_id))

"""Endpoint para registrar asistencias (descuenta el cupo en una transacción)."""

from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from ..db import get_db
from ..repositories.base import a_salida
from ..schemas import AsistenciaCrear, AsistenciaSalida
from ..services.asistencias import AsistenciasService

router = APIRouter(prefix="/asistencias", tags=["Asistencias"])


def servicio(db: Database = Depends(get_db)) -> AsistenciasService:
    return AsistenciasService(db)


@router.post(
    "", response_model=AsistenciaSalida, status_code=status.HTTP_201_CREATED,
    summary="Registrar una asistencia y descontar un cupo",
    description="Inserta la asistencia y descuenta el cupo del cliente en una única transacción multidocumento.",
    responses={
        400: {"description": "ID de cliente mal formado"},
        404: {"description": "El cliente no existe"},
        409: {"description": "Cliente no activo, sin plan, con plan vencido o sin cupos"},
        422: {"description": "La actividad no está incluida en el plan"},
    },
)
def registrar_asistencia(datos: AsistenciaCrear, svc: AsistenciasService = Depends(servicio)):
    return a_salida(svc.registrar(datos))

"""
Endpoints de clientes (entidad principal del CRUD).

La capa de rutas solo recibe el pedido HTTP, se lo pasa al servicio y arma la
respuesta. No accede a Mongo directamente.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from pymongo.database import Database

from ..db import get_db
from ..repositories.base import a_salida
from ..schemas import (AsignarPlan, AsistenciaSalida, ClienteActualizar, ClienteCrear,
                       ClienteSalida, Estado, ListaClientes)
from ..services.clientes import ClientesService

router = APIRouter(prefix="/clientes", tags=["Clientes"])

ERRORES_ID = {400: {"description": "ID mal formado"}, 404: {"description": "El cliente no existe"}}


def servicio(db: Database = Depends(get_db)) -> ClientesService:
    return ClientesService(db)


@router.post("", response_model=ClienteSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear un cliente",
             responses={409: {"description": "Ya existe un cliente con ese DNI"},
                        422: {"description": "Datos inválidos"}})
def crear_cliente(datos: ClienteCrear, svc: ClientesService = Depends(servicio)):
    return a_salida(svc.crear(datos))


@router.get("", response_model=ListaClientes, summary="Listar clientes con filtros")
def listar_clientes(
    estado: Optional[Estado] = Query(None, description="activo, inactivo o suspendido"),
    plan: Optional[str] = Query(None, description="Nombre del plan, por ejemplo '12 clases'"),
    cupos_max: Optional[int] = Query(None, ge=0, description="Clientes con esta cantidad de cupos o menos"),
    vigente: Optional[bool] = Query(None, description="true: plan vigente · false: plan vencido"),
    buscar: Optional[str] = Query(None, min_length=2, description="Texto a buscar en nombre, apellido o DNI"),
    limite: int = Query(20, ge=1, le=100, description="Cantidad máxima de resultados"),
    salto: int = Query(0, ge=0, description="Cantidad de resultados a saltear (paginación)"),
    svc: ClientesService = Depends(servicio),
):
    total, clientes = svc.listar(estado, plan, cupos_max, vigente, buscar, limite, salto)
    return {"total": total, "limite": limite, "salto": salto, "resultados": [a_salida(c) for c in clientes]}


@router.get("/{cliente_id}", response_model=ClienteSalida, summary="Obtener un cliente por ID",
            responses=ERRORES_ID)
def obtener_cliente(cliente_id: str, svc: ClientesService = Depends(servicio)):
    return a_salida(svc.obtener(cliente_id))


@router.patch("/{cliente_id}", response_model=ClienteSalida, summary="Actualizar datos de un cliente",
              responses={**ERRORES_ID, 409: {"description": "El DNI nuevo ya es de otro cliente"},
                         422: {"description": "Datos inválidos"}})
def actualizar_cliente(cliente_id: str, cambios: ClienteActualizar, svc: ClientesService = Depends(servicio)):
    return a_salida(svc.actualizar(cliente_id, cambios))


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar un cliente y su historial de asistencias", responses=ERRORES_ID)
def eliminar_cliente(cliente_id: str, svc: ClientesService = Depends(servicio)):
    svc.eliminar(cliente_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{cliente_id}/plan", response_model=ClienteSalida, summary="Asignar o renovar el plan",
            responses={**ERRORES_ID, 409: {"description": "El cliente no está activo"},
                       422: {"description": "El plan está discontinuado"}})
def asignar_plan(cliente_id: str, datos: AsignarPlan, svc: ClientesService = Depends(servicio)):
    return a_salida(svc.asignar_plan(cliente_id, datos.plan_id))


@router.get("/{cliente_id}/asistencias", response_model=List[AsistenciaSalida],
            summary="Historial de asistencias del cliente (más reciente primero)", responses=ERRORES_ID)
def historial(cliente_id: str, limite: int = Query(50, ge=1, le=500), svc: ClientesService = Depends(servicio)):
    return [a_salida(a) for a in svc.historial(cliente_id, limite)]

"""
Modelos de entrada y salida de la API (Pydantic).

Validan los datos ANTES de llegar a la base. MongoDB además tiene su propio
validador $jsonSchema (seed.py) como segunda línea de defensa.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Estado = Literal["activo", "inactivo", "suspendido"]


# Funciones que crean la definición de cada campo (cada modelo necesita su propia copia)
def DNI(**kw):
    return Field(pattern=r"^[0-9]{7,8}$", description="7 u 8 dígitos, sin puntos", examples=["42123456"], **kw)


def NOMBRE(**kw):
    return Field(min_length=1, max_length=60, **kw)


def EMAIL(**kw):
    return Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120, examples=["lucia@mail.com"], **kw)


def TELEFONO(**kw):
    return Field(pattern=r"^[0-9+\- ]{6,20}$", examples=["3515551234"], **kw)


def OBJETIVOS():
    return Field(default=None, max_length=10, examples=[["hyrox", "fuerza"]])


class Entrada(BaseModel):
    # extra="forbid": un campo que no existe (por ejemplo "cupos_restantes") da error 422
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Clientes ---------------------------------------------------------------

class ContactoEmergencia(Entrada):
    nombre: str = NOMBRE()
    telefono: str = TELEFONO()


def _normalizar_objetivos(valor):
    if valor is None:
        return None
    vistos = []
    for objetivo in valor:
        objetivo = objetivo.strip().lower()
        if objetivo and objetivo not in vistos:
            vistos.append(objetivo)
    return vistos


class ClienteCrear(Entrada):
    dni: str = DNI()
    nombre: str = NOMBRE()
    apellido: str = NOMBRE()
    email: Optional[str] = EMAIL(default=None)
    telefono: Optional[str] = TELEFONO(default=None)
    objetivos: Optional[List[str]] = OBJETIVOS()
    contacto_emergencia: Optional[ContactoEmergencia] = None
    estado: Estado = "activo"

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "dni": "44555666",
        "nombre": "Joaquín",
        "apellido": "Maldonado",
        "email": "joaquin@mail.com",
        "telefono": "3515551234",
        "objetivos": ["hyrox", "fuerza"],
        "contacto_emergencia": {"nombre": "Ana Maldonado", "telefono": "3515559999"},
    }]})

    @field_validator("objetivos")
    @classmethod
    def normalizar(cls, v):
        return _normalizar_objetivos(v)


class ClienteActualizar(Entrada):
    """
    Actualización parcial (PATCH): solo se modifican los campos enviados.
    Mandar null en un campo opcional lo borra del documento.
    El plan no se cambia acá sino con PUT /clientes/{id}/plan.
    """
    dni: Optional[str] = DNI(default=None)
    nombre: Optional[str] = NOMBRE(default=None)
    apellido: Optional[str] = NOMBRE(default=None)
    email: Optional[str] = EMAIL(default=None)
    telefono: Optional[str] = TELEFONO(default=None)
    objetivos: Optional[List[str]] = OBJETIVOS()
    contacto_emergencia: Optional[ContactoEmergencia] = None
    estado: Optional[Estado] = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"telefono": "3517778888", "email": None}]})

    @field_validator("objetivos")
    @classmethod
    def normalizar(cls, v):
        return _normalizar_objetivos(v)

    @model_validator(mode="after")
    def revisar(self):
        if not self.model_fields_set:
            raise ValueError("Hay que enviar al menos un campo para actualizar")
        obligatorios = {"dni", "nombre", "apellido", "estado"}
        for campo in obligatorios & self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' es obligatorio y no se puede borrar")
        return self


class AsignarPlan(Entrada):
    plan_id: str = Field(description="ID de un plan activo del catálogo (GET /planes)")


class PlanActualSalida(BaseModel):
    plan_id: str
    nombre: str
    precio_pagado: int
    cupos_totales: Optional[int] = Field(description="null en el plan libre")
    cupos_restantes: Optional[int] = Field(description="null en el plan libre")
    fecha_inicio: datetime
    fecha_vencimiento: datetime


class ClienteSalida(BaseModel):
    id: str
    dni: str
    nombre: str
    apellido: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    objetivos: Optional[List[str]] = None
    contacto_emergencia: Optional[dict] = None
    estado: Estado
    fecha_alta: datetime
    plan_actual: Optional[PlanActualSalida] = None


class ListaClientes(BaseModel):
    total: int = Field(description="Cantidad de clientes que cumplen los filtros")
    limite: int
    salto: int
    resultados: List[ClienteSalida]


# --- Planes -----------------------------------------------------------------

class PlanSalida(BaseModel):
    id: str
    nombre: str
    precio: int
    cupos_mensuales: Optional[int] = None
    duracion_dias: int
    actividades_incluidas: List[str]
    activo: bool
    descripcion: Optional[str] = None


# --- Asistencias ------------------------------------------------------------

class AsistenciaCrear(Entrada):
    cliente_id: str
    actividad: str = Field(min_length=1, max_length=40, examples=["crossfit"])
    coach: Optional[str] = Field(default=None, min_length=1, max_length=40)

    @field_validator("actividad")
    @classmethod
    def minusculas(cls, v):
        return v.lower()


class AsistenciaSalida(BaseModel):
    id: str
    cliente_id: str
    fecha_hora: datetime
    actividad: str
    coach: Optional[str] = None
    cupos_restantes_post: Optional[int] = Field(default=None, description="Cupos que le quedaron al cliente")

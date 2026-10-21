"""
API del gimnasio — TP Integrador MongoDB.

Capas:
  routers/       reciben el pedido HTTP y arman la respuesta
  services/      reglas de negocio y transacciones
  repositories/  único lugar que accede a MongoDB

Documentación interactiva (Swagger): http://localhost:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, WriteError

from .db import get_db
from .errores import ErrorDominio
from .routers import asistencias, clientes, planes

app = FastAPI(
    title="API Gimnasio — TP MongoDB",
    description="Gestión de clientes, planes por cupos y asistencias. Base de Datos Aplicada · UCC.",
    version="1.0.0",
)

app.include_router(clientes.router)
app.include_router(asistencias.router)
app.include_router(planes.router)


# --- Traducción de errores a respuestas HTTP -----------------------------------

@app.exception_handler(ErrorDominio)
def error_dominio(request: Request, error: ErrorDominio):
    return JSONResponse(status_code=error.status_code, content={"detalle": error.mensaje})


@app.exception_handler(RequestValidationError)
def error_validacion(request: Request, error: RequestValidationError):
    errores = []
    for e in error.errors():
        campo = ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path"))
        errores.append({"campo": campo or None, "error": e["msg"]})
    return JSONResponse(status_code=422, content={"detalle": "Datos inválidos", "errores": errores})


@app.exception_handler(WriteError)
def error_escritura(request: Request, error: WriteError):
    # Código 121: el documento no pasó el validador $jsonSchema de la colección
    if error.code == 121:
        return JSONResponse(status_code=422, content={"detalle": "El documento no cumple la validación de la base"})
    return JSONResponse(status_code=500, content={"detalle": "Error al escribir en la base"})


@app.exception_handler(ServerSelectionTimeoutError)
def sin_conexion(request: Request, error: ServerSelectionTimeoutError):
    return JSONResponse(status_code=503, content={"detalle": "No hay conexión con MongoDB"})


@app.exception_handler(PyMongoError)
def error_mongo(request: Request, error: PyMongoError):
    return JSONResponse(status_code=500, content={"detalle": "Error de la base de datos"})


@app.exception_handler(Exception)
def error_inesperado(request: Request, error: Exception):
    return JSONResponse(status_code=500, content={"detalle": "Error interno del servidor"})


# --- Rutas generales -------------------------------------------------------------

@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/docs")


@app.get("/health", tags=["General"], summary="Estado de la API y de la conexión a MongoDB")
def health():
    get_db().command("ping")
    return {"api": "ok", "mongodb": "ok"}

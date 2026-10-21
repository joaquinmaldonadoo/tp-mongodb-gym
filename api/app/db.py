"""Conexión a MongoDB y ayuda para ejecutar transacciones."""

from datetime import datetime, timezone
from typing import Callable, TypeVar

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database

from . import config

T = TypeVar("T")

_cliente = None


def get_cliente() -> MongoClient:
    """Devuelve un único MongoClient para toda la aplicación (maneja su propio pool de conexiones)."""
    global _cliente
    if _cliente is None:
        # tz_aware=True: las fechas vuelven con zona horaria (UTC) y se comparan bien con datetime.now(timezone.utc)
        _cliente = MongoClient(config.MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=5000)
    return _cliente


def get_db() -> Database:
    return get_cliente()[config.MONGO_DB]


def en_transaccion(db: Database, operacion: Callable[[ClientSession], T]) -> T:
    """
    Ejecuta `operacion(session)` dentro de una transacción multidocumento.

    with_transaction hace commit si la función termina bien, abort si lanza una
    excepción, y reintenta solo ante errores transitorios (por ejemplo, un
    conflicto de escritura con otra transacción que tocó el mismo documento).
    Requiere un replica set: por eso Mongo se levanta con --replSet rs0.
    """
    with db.client.start_session() as session:
        return session.with_transaction(operacion)


def ahora() -> datetime:
    """Fecha y hora actual en UTC, redondeada a milisegundos (la precisión con la que Mongo guarda fechas)."""
    t = datetime.now(timezone.utc)
    return t.replace(microsecond=t.microsecond // 1000 * 1000)

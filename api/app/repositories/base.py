"""Utilidades compartidas por los repositorios."""

from bson import ObjectId
from bson.errors import InvalidId

from ..errores import IdInvalido


def a_object_id(valor: str, que: str = "ID") -> ObjectId:
    """Convierte el string que llega por la URL en un ObjectId, o lanza IdInvalido."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise IdInvalido(f"{que} inválido: '{valor}' no es un ObjectId de 24 caracteres hexadecimales")


def a_salida(documento):
    """Convierte un documento de Mongo en un dict listo para la API: _id -> id y ObjectId -> str."""
    if documento is None:
        return None

    def convertir(valor):
        if isinstance(valor, ObjectId):
            return str(valor)
        if isinstance(valor, dict):
            return {k: convertir(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [convertir(v) for v in valor]
        return valor

    salida = convertir(dict(documento))
    salida["id"] = salida.pop("_id")
    return salida

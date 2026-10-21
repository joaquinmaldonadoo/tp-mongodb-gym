"""
Errores del dominio. Los servicios lanzan estos errores sin saber nada de HTTP;
main.py los traduce al código de estado que corresponde.
"""


class ErrorDominio(Exception):
    status_code = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class IdInvalido(ErrorDominio):
    """El identificador no tiene el formato de un ObjectId."""
    status_code = 400


class NoEncontrado(ErrorDominio):
    status_code = 404


class Conflicto(ErrorDominio):
    """La operación choca con el estado actual de los datos (DNI repetido, sin cupos, plan vencido)."""
    status_code = 409


class ReglaDeNegocio(ErrorDominio):
    """Los datos tienen el formato correcto pero no tienen sentido para el negocio."""
    status_code = 422

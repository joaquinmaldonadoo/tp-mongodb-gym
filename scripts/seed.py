"""
Carga inicial de la base `gym`.

Borra la base, crea las colecciones con validación de esquema ($jsonSchema),
genera datos de prueba coherentes y los inserta. También exporta los datos
a data/*.json como evidencia.

Uso (desde la carpeta del proyecto, con Mongo levantado):
    python scripts/seed.py

Los datos se generan con una semilla fija (random.seed(42)), así que siempre
salen los mismos clientes. Las fechas son relativas al día en que se corre el
script, para que las consultas de "próximos 7 días" o "último mes" siempre
devuelvan resultados.
"""

import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId, json_util
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
MONGO_DB = os.getenv("MONGO_DB", "gym")

rng = random.Random(42)

# Córdoba es UTC-3. Mongo guarda las fechas en UTC.
TZ_LOCAL = timezone(timedelta(hours=-3))
AHORA = datetime.now(timezone.utc).replace(microsecond=0)
HOY_LOCAL = AHORA.astimezone(TZ_LOCAL).replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Validadores de esquema (extensión opcional de la consigna)
# ---------------------------------------------------------------------------

INT = ["int", "long"]

VALIDADOR_PLANES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["nombre", "precio", "duracion_dias", "actividades_incluidas", "activo"],
        "properties": {
            "nombre": {"bsonType": "string", "minLength": 1},
            "precio": {"bsonType": INT, "minimum": 0},
            "cupos_mensuales": {"bsonType": INT, "minimum": 1},
            "duracion_dias": {"bsonType": INT, "minimum": 1},
            "actividades_incluidas": {"bsonType": "array", "minItems": 1, "items": {"bsonType": "string"}},
            "activo": {"bsonType": "bool"},
            "descripcion": {"bsonType": "string"},
        },
    }
}

VALIDADOR_CLIENTES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["dni", "nombre", "apellido", "estado", "fecha_alta"],
        "properties": {
            "dni": {"bsonType": "string", "pattern": "^[0-9]{7,8}$"},
            "nombre": {"bsonType": "string", "minLength": 1},
            "apellido": {"bsonType": "string", "minLength": 1},
            "email": {"bsonType": "string", "pattern": "^.+@.+\\..+$"},
            "telefono": {"bsonType": "string"},
            "fecha_alta": {"bsonType": "date"},
            "estado": {"enum": ["activo", "inactivo", "suspendido"]},
            "plan_actual": {
                "bsonType": "object",
                "required": ["plan_id", "nombre", "precio_pagado", "cupos_totales",
                             "cupos_restantes", "fecha_inicio", "fecha_vencimiento"],
                "properties": {
                    "plan_id": {"bsonType": "objectId"},
                    "nombre": {"bsonType": "string"},
                    "precio_pagado": {"bsonType": INT, "minimum": 0},
                    # null = plan libre (sin límite de cupos)
                    "cupos_totales": {"bsonType": INT + ["null"]},
                    "cupos_restantes": {"bsonType": INT + ["null"], "minimum": 0},
                    "fecha_inicio": {"bsonType": "date"},
                    "fecha_vencimiento": {"bsonType": "date"},
                },
            },
            "objetivos": {"bsonType": "array", "items": {"bsonType": "string"}},
            "contacto_emergencia": {
                "bsonType": "object",
                "required": ["nombre", "telefono"],
                "properties": {
                    "nombre": {"bsonType": "string"},
                    "telefono": {"bsonType": "string"},
                },
            },
        },
    }
}

VALIDADOR_ASISTENCIAS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["cliente_id", "fecha_hora", "actividad"],
        "properties": {
            "cliente_id": {"bsonType": "objectId"},
            "fecha_hora": {"bsonType": "date"},
            "actividad": {"bsonType": "string"},
            "cupos_restantes_post": {"bsonType": INT, "minimum": 0},
            "coach": {"bsonType": "string"},
        },
    }
}


# ---------------------------------------------------------------------------
# Catálogo de planes
# ---------------------------------------------------------------------------

def generar_planes():
    return [
        {"_id": ObjectId(), "nombre": "8 clases", "precio": 30000, "cupos_mensuales": 8,
         "duracion_dias": 30, "actividades_incluidas": ["crossfit", "funcional", "musculacion"], "activo": True},
        {"_id": ObjectId(), "nombre": "12 clases", "precio": 38000, "cupos_mensuales": 12,
         "duracion_dias": 30, "actividades_incluidas": ["crossfit", "funcional", "musculacion", "hyrox"], "activo": True},
        {"_id": ObjectId(), "nombre": "16 clases", "precio": 45000, "cupos_mensuales": 16,
         "duracion_dias": 30, "actividades_incluidas": ["crossfit", "funcional", "musculacion", "hyrox", "movilidad"], "activo": True},
        # Caso límite: plan sin cupos_mensuales (no descuenta)
        {"_id": ObjectId(), "nombre": "Libre", "precio": 55000,
         "duracion_dias": 30, "actividades_incluidas": ["crossfit", "funcional", "musculacion", "hyrox", "movilidad"],
         "activo": True, "descripcion": "Acceso ilimitado a todas las actividades"},
        {"_id": ObjectId(), "nombre": "Estudiante 8 clases", "precio": 25000, "cupos_mensuales": 8,
         "duracion_dias": 30, "actividades_incluidas": ["funcional", "musculacion"], "activo": True,
         "descripcion": "Requiere certificado de alumno regular"},
        # Caso límite: plan dado de baja del catálogo
        {"_id": ObjectId(), "nombre": "4 clases", "precio": 18000, "cupos_mensuales": 4,
         "duracion_dias": 30, "actividades_incluidas": ["musculacion"], "activo": False,
         "descripcion": "Discontinuado en 2026"},
    ]


# ---------------------------------------------------------------------------
# Clientes y asistencias
# ---------------------------------------------------------------------------

NOMBRES = ["Lucía", "Martina", "Sofía", "Valentina", "Camila", "Julieta", "Agustina", "Florencia",
           "Micaela", "Carolina", "Paula", "Ailín", "Rocío", "Milagros", "Abril", "Catalina",
           "Mateo", "Santiago", "Joaquín", "Tomás", "Benjamín", "Facundo", "Nicolás", "Lautaro",
           "Franco", "Ignacio", "Juan Cruz", "Agustín", "Gonzalo", "Matías", "Bruno", "Thiago"]
APELLIDOS = ["González", "Rodríguez", "Gómez", "Fernández", "López", "Díaz", "Martínez", "Pérez",
             "García", "Sánchez", "Romero", "Sosa", "Álvarez", "Torres", "Ruiz", "Ramírez",
             "Flores", "Acosta", "Benítez", "Medina", "Herrera", "Suárez", "Aguirre", "Giménez",
             "Molina", "Castro", "Ortiz", "Silva", "Núñez", "Luna", "Juárez", "Cabrera"]
OBJETIVOS = ["fuerza", "hyrox", "bajar de peso", "resistencia", "movilidad", "competir", "salud"]
COACHES = {
    "crossfit": ["Nico", "Vale"],
    "funcional": ["Vale", "Lucho"],
    "musculacion": ["Lucho", "Pato"],
    "hyrox": ["Nico"],
    "movilidad": ["Sol"],
}
# Horas locales en las que se entrena, con peso (picos a la mañana temprano y después del trabajo)
HORAS = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
PESOS_HORA = [9, 8, 5, 3, 3, 4, 2, 1, 1, 2, 5, 10, 12, 9, 4]
# Algunos días van más que otros (lunes=0 ... domingo=6); el gym abre de lunes a sábado
PESOS_DIA = [10, 8, 9, 7, 5, 3, 0]

dnis_usados = set()


def nuevo_dni():
    while True:
        dni = str(rng.randint(30_000_000, 47_999_999))
        if dni not in dnis_usados:
            dnis_usados.add(dni)
            return dni


def sin_tildes(texto):
    tabla = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return texto.translate(tabla).lower().replace(" ", "")


def generar_cliente(categoria):
    nombre = rng.choice(NOMBRES)
    apellido = rng.choice(APELLIDOS)
    cliente = {
        "_id": ObjectId(),
        "dni": nuevo_dni(),
        "nombre": nombre,
        "apellido": apellido,
        "fecha_alta": None,  # se completa abajo
        "estado": "activo",
    }
    # Atributos opcionales: no todos los clientes los tienen
    if rng.random() < 0.85:
        cliente["email"] = f"{sin_tildes(nombre)}.{sin_tildes(apellido)}{rng.randint(1, 99)}@mail.com"
    if rng.random() < 0.9:
        cliente["telefono"] = f"351{rng.randint(4000000, 6999999)}"
    if rng.random() < 0.7:
        cliente["objetivos"] = rng.sample(OBJETIVOS, rng.randint(1, 3))
    if rng.random() < 0.5:
        cliente["contacto_emergencia"] = {
            "nombre": f"{rng.choice(NOMBRES)} {apellido}",
            "telefono": f"351{rng.randint(4000000, 6999999)}",
        }
    if categoria == "inactivo":
        cliente["estado"] = "inactivo"
    if categoria == "suspendido":
        cliente["estado"] = "suspendido"
    return cliente


def elegir_dia(inicio, fin, dias_ocupados):
    """Elige un día entre inicio y fin (inclusive) respetando los pesos por día de la semana."""
    candidatos = []
    dia = inicio
    while dia <= fin:
        if dia not in dias_ocupados and PESOS_DIA[dia.weekday()] > 0:
            candidatos.append(dia)
        dia += timedelta(days=1)
    if not candidatos:
        return None
    return rng.choices(candidatos, weights=[PESOS_DIA[d.weekday()] for d in candidatos])[0]


def dias_habiles(inicio, fin):
    n, dia = 0, inicio
    while dia <= fin:
        if PESOS_DIA[dia.weekday()] > 0:
            n += 1
        dia += timedelta(days=1)
    return n


def generar_asistencias(cliente, plan, inicio_local, fin_local, cantidad):
    """Genera `cantidad` asistencias (una por día como máximo) entre dos fechas locales."""
    asistencias = []
    dias_ocupados = set()
    for _ in range(cantidad):
        dia = elegir_dia(inicio_local, fin_local, dias_ocupados)
        if dia is None:
            break
        dias_ocupados.add(dia)
        hora = rng.choices(HORAS, weights=PESOS_HORA)[0]
        momento_local = dia.replace(hour=hora, minute=rng.choice([0, 5, 10, 15, 30, 35, 45]))
        actividades = plan["actividades_incluidas"]
        pesos = [3 if a == "hyrox" and "hyrox" in cliente.get("objetivos", []) else 1 for a in actividades]
        actividad = rng.choices(actividades, weights=pesos)[0]
        asistencia = {
            "_id": ObjectId(),
            "cliente_id": cliente["_id"],
            "fecha_hora": momento_local.astimezone(timezone.utc),
            "actividad": actividad,
        }
        if rng.random() < 0.85:  # coach opcional (musculación libre a veces no tiene)
            asistencia["coach"] = rng.choice(COACHES[actividad])
        asistencias.append(asistencia)

    asistencias.sort(key=lambda a: a["fecha_hora"])
    # cupos_restantes_post: cuántos cupos le quedaban después de cada asistencia
    if plan.get("cupos_mensuales"):
        for i, a in enumerate(asistencias, start=1):
            a["cupos_restantes_post"] = plan["cupos_mensuales"] - i
    return asistencias


def asignar_plan(cliente, plan, inicio_local, usados_objetivo, forzar_agotado=False):
    """Embebe una copia del plan en el cliente y genera las asistencias del período."""
    vencimiento_local = inicio_local + timedelta(days=plan["duracion_dias"])
    ayer_local = HOY_LOCAL - timedelta(days=1)
    fin_asistencias = min(vencimiento_local - timedelta(days=1), ayer_local)

    disponibles = dias_habiles(inicio_local, fin_asistencias)
    cupos = plan.get("cupos_mensuales")
    if cupos is not None:
        usados = cupos if forzar_agotado else min(usados_objetivo, cupos)
        usados = min(usados, disponibles)
    else:
        usados = min(usados_objetivo, disponibles)

    asistencias = generar_asistencias(cliente, plan, inicio_local, fin_asistencias, usados)
    usados = len(asistencias)

    precio = plan["precio"]
    if rng.random() < 0.15:  # algunos pagaron con descuento (promo, pago anual, etc.)
        precio = int(precio * 0.9)

    cliente["plan_actual"] = {
        "plan_id": plan["_id"],
        "nombre": plan["nombre"],
        "precio_pagado": precio,
        "cupos_totales": cupos,
        "cupos_restantes": (cupos - usados) if cupos is not None else None,
        "fecha_inicio": inicio_local.astimezone(timezone.utc),
        "fecha_vencimiento": vencimiento_local.astimezone(timezone.utc),
    }
    return asistencias


def generar_datos():
    planes = generar_planes()
    por_nombre = {p["nombre"]: p for p in planes}
    planes_vigentes = ["8 clases", "12 clases", "16 clases", "Estudiante 8 clases", "Libre"]
    pesos_planes = [30, 35, 12, 13, 10]

    clientes, asistencias = [], []

    def alta(cliente, dias_atras_min, dias_atras_max):
        dias = rng.randint(dias_atras_min, dias_atras_max)
        cliente["fecha_alta"] = (HOY_LOCAL - timedelta(days=dias)).astimezone(timezone.utc)

    # 1) Clientes activos con plan vigente (la mayoría)
    for i in range(66):
        c = generar_cliente("activo")
        alta(c, 30, 600)
        plan = por_nombre[rng.choices(planes_vigentes, weights=pesos_planes)[0]]
        inicio = HOY_LOCAL - timedelta(days=rng.randint(2, 27))
        transcurrido = (HOY_LOCAL - inicio).days / plan["duracion_dias"]
        base = plan.get("cupos_mensuales") or 20
        # Uso proporcional al tiempo transcurrido, con variación (hay constantes y hay colgados)
        usados = max(0, round(base * transcurrido * rng.uniform(0.3, 1.3)))
        asistencias += asignar_plan(c, plan, inicio, usados, forzar_agotado=(i < 4))
        clientes.append(c)

    # 2) Clientes con plan vencido que siguen figurando como activos (RF4 tiene que rechazarlos)
    for _ in range(10):
        c = generar_cliente("activo")
        alta(c, 60, 500)
        plan = por_nombre[rng.choice(["8 clases", "12 clases", "Estudiante 8 clases"])]
        inicio = HOY_LOCAL - timedelta(days=rng.randint(35, 55))
        asistencias += asignar_plan(c, plan, inicio, rng.randint(2, plan["cupos_mensuales"]))
        clientes.append(c)

    # 3) Altas recientes sin plan asignado todavía
    for _ in range(7):
        c = generar_cliente("activo")
        alta(c, 0, 6)
        clientes.append(c)

    # 4) Clientes dados de baja o suspendidos
    for categoria in ["inactivo"] * 5 + ["suspendido"] * 2:
        c = generar_cliente(categoria)
        alta(c, 200, 700)
        if rng.random() < 0.5:  # algunos conservan el último plan que tuvieron (el del catálogo viejo)
            plan = por_nombre["4 clases"]
            inicio = HOY_LOCAL - timedelta(days=rng.randint(90, 180))
            asistencias += asignar_plan(c, plan, inicio, rng.randint(0, 4))
        clientes.append(c)

    # 5) Casos límite puntuales
    # DNI de 7 dígitos, sin email ni teléfono, nombre compuesto
    c = generar_cliente("activo")
    c.update({"dni": "8456123", "nombre": "María José", "apellido": "De la Fuente"})
    c.pop("email", None)
    c.pop("telefono", None)
    alta(c, 900, 900)
    asistencias += asignar_plan(c, por_nombre["8 clases"], HOY_LOCAL - timedelta(days=5), 1)
    clientes.append(c)

    # Cliente con todos los objetivos y plan que vence mañana
    c = generar_cliente("activo")
    c["objetivos"] = list(OBJETIVOS)
    alta(c, 400, 400)
    asistencias += asignar_plan(c, por_nombre["16 clases"], HOY_LOCAL - timedelta(days=29), 14)
    clientes.append(c)

    return planes, clientes, asistencias


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def exportar(nombre, documentos):
    carpeta = Path(__file__).resolve().parent.parent / "data"
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / f"{nombre}.json"
    ruta.write_text(json_util.dumps(documentos, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    planes, clientes, asistencias = generar_datos()

    cliente = MongoClient(MONGO_URI)
    db = cliente[MONGO_DB]

    print(f"Conectado a {MONGO_URI} — base '{MONGO_DB}'")
    cliente.drop_database(MONGO_DB)
    print("Base anterior borrada")

    db.create_collection("planes", validator=VALIDADOR_PLANES)
    db.create_collection("clientes", validator=VALIDADOR_CLIENTES)
    db.create_collection("asistencias", validator=VALIDADOR_ASISTENCIAS)
    print("Colecciones creadas con validación de esquema")

    # Índice único: dos clientes no pueden tener el mismo DNI (es una regla del negocio,
    # por eso va en la carga y no solo en el script de índices)
    db.clientes.create_index([("dni", ASCENDING)], unique=True, name="dni_unico")

    db.planes.insert_many(planes)
    db.clientes.insert_many(clientes)
    db.asistencias.insert_many(asistencias)

    exportar("planes", planes)
    exportar("clientes", clientes)
    exportar("asistencias", asistencias)

    total = len(planes) + len(clientes) + len(asistencias)
    print(f"Insertados: {len(planes)} planes, {len(clientes)} clientes, {len(asistencias)} asistencias ({total} documentos)")
    print("Datos exportados en data/*.json")


if __name__ == "__main__":
    main()

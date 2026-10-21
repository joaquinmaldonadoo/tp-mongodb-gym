"""
Verifica la cantidad y la consistencia básica de los datos cargados.

Uso:
    python scripts/verificar.py

Chequea:
  1. Cantidad de documentos por colección.
  2. Que no haya DNI duplicados.
  3. Que toda asistencia apunte a un cliente que existe.
  4. Que en cada cliente: cupos_totales - cupos_restantes == asistencias del período.
  5. Que no haya cupos negativos ni asistencias con fecha futura.
  6. Que el validador de esquema rechace un documento inválido.
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import WriteError

load_dotenv()
db = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"))[os.getenv("MONGO_DB", "gym")]

errores = 0


def chequeo(descripcion, ok, detalle=""):
    global errores
    marca = "OK   " if ok else "ERROR"
    if not ok:
        errores += 1
    print(f"[{marca}] {descripcion}" + (f" — {detalle}" if detalle else ""))


# 1. Cantidades
n_planes = db.planes.count_documents({})
n_clientes = db.clientes.count_documents({})
n_asistencias = db.asistencias.count_documents({})
total = n_planes + n_clientes + n_asistencias
print(f"planes: {n_planes} | clientes: {n_clientes} | asistencias: {n_asistencias} | total: {total}\n")
chequeo("Al menos 100 documentos en total", total >= 100, f"{total} documentos")

# 2. DNI duplicados
duplicados = list(db.clientes.aggregate([
    {"$group": {"_id": "$dni", "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}},
]))
chequeo("No hay DNI duplicados", not duplicados, f"{len(duplicados)} duplicados")

# 3. Asistencias huérfanas (cliente_id que no existe)
huerfanas = list(db.asistencias.aggregate([
    {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "c"}},
    {"$match": {"c": {"$size": 0}}},
    {"$count": "n"},
]))
chequeo("Toda asistencia apunta a un cliente existente", not huerfanas,
        f"{huerfanas[0]['n']} huérfanas" if huerfanas else "")

# 4. Cupos usados == asistencias dentro del período del plan
inconsistentes = list(db.clientes.aggregate([
    {"$match": {"plan_actual.cupos_totales": {"$ne": None}}},
    {"$lookup": {
        "from": "asistencias",
        "let": {"id": "$_id", "ini": "$plan_actual.fecha_inicio", "fin": "$plan_actual.fecha_vencimiento"},
        "pipeline": [{"$match": {"$expr": {"$and": [
            {"$eq": ["$cliente_id", "$$id"]},
            {"$gte": ["$fecha_hora", "$$ini"]},
            {"$lt": ["$fecha_hora", "$$fin"]},
        ]}}}],
        "as": "periodo",
    }},
    {"$project": {
        "dni": 1,
        "usados": {"$subtract": ["$plan_actual.cupos_totales", "$plan_actual.cupos_restantes"]},
        "asistencias": {"$size": "$periodo"},
    }},
    {"$match": {"$expr": {"$ne": ["$usados", "$asistencias"]}}},
]))
chequeo("Cupos usados coinciden con las asistencias del período", not inconsistentes,
        f"{len(inconsistentes)} clientes no coinciden" if inconsistentes else "")

# 5. Valores imposibles
negativos = db.clientes.count_documents({"plan_actual.cupos_restantes": {"$lt": 0}})
chequeo("No hay cupos negativos", negativos == 0, f"{negativos} clientes")
futuras = db.asistencias.count_documents({"fecha_hora": {"$gt": datetime.now(timezone.utc)}})
chequeo("No hay asistencias con fecha futura", futuras == 0, f"{futuras} asistencias")

# 6. El validador rechaza documentos inválidos
try:
    db.clientes.insert_one({"dni": "abc", "nombre": "Prueba", "apellido": "Inválida",
                            "estado": "activo", "fecha_alta": datetime.now(timezone.utc)})
    db.clientes.delete_one({"dni": "abc"})
    chequeo("El validador rechaza un DNI con letras", False, "se insertó igual")
except WriteError:
    chequeo("El validador rechaza un DNI con letras", True)

# Casos límite presentes en los datos
print("\nCasos límite:")
print(f"  Clientes sin plan asignado:     {db.clientes.count_documents({'plan_actual': {'$exists': False}})}")
print(f"  Clientes sin email:             {db.clientes.count_documents({'email': {'$exists': False}})}")
print(f"  Clientes con 0 cupos:           {db.clientes.count_documents({'plan_actual.cupos_restantes': 0})}")
print(f"  Clientes con plan libre:        {db.clientes.count_documents({'plan_actual.cupos_totales': None, 'plan_actual': {'$exists': True}})}")
print(f"  Clientes con plan vencido:      {db.clientes.count_documents({'plan_actual.fecha_vencimiento': {'$lt': datetime.now(timezone.utc)}})}")
print(f"  Planes inactivos en catálogo:   {db.planes.count_documents({'activo': False})}")

print(f"\n{'Todo en orden' if errores == 0 else f'{errores} chequeos fallaron'}")

"""Configuración leída de variables de entorno (o del archivo .env en la raíz del proyecto)."""

import os

from dotenv import load_dotenv

# No pisa variables que ya existan: dentro de Docker manda lo que define el compose
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
MONGO_DB = os.getenv("MONGO_DB", "gym")

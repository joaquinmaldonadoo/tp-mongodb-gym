# TP Integrador MongoDB — Gestión de cupos y asistencias de un gimnasio

Base de Datos Aplicada · UCC · Ingeniería en Informática

Sistema que registra clientes de un gimnasio, sus planes por cupos y sus asistencias, descontando cupos de forma consistente. El diseño completo está en [docs/diseno.md](docs/diseno.md).

## Estructura del repo

```
docs/        Documento de diseño (entrega 1) e informe
data/        Datos de prueba (JSON)
scripts/     Scripts de creación y carga de la base
queries/     Las 10 consultas comentadas y los índices
api/         API con FastAPI y capa de repositorios
analisis/    Notebook de análisis de datos
```

## Requisitos

- Docker Desktop
- MongoDB Compass (opcional, para ver los datos)

## Levantar el entorno

1. Copiar la configuración de ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Iniciar MongoDB:

   ```bash
   docker compose up -d
   ```

3. Verificar que esté funcionando (tiene que decir `healthy` después de unos segundos):

   ```bash
   docker compose ps
   ```

4. Conectarse desde Compass con:

   ```
   mongodb://localhost:27017/?directConnection=true
   ```

## Detener el entorno

```bash
docker compose down        # apaga, los datos se conservan
docker compose down -v     # apaga y borra los datos (reinicio desde cero)
```

## Por qué un replica set

MongoDB solo permite transacciones multidocumento en un replica set. El caso de consistencia del TP (registrar asistencia y descontar un cupo) usa una transacción, así que Mongo se levanta como replica set de un nodo (`rs0`). El healthcheck del compose lo inicializa automáticamente.

## Cargar los datos de prueba

Pendiente (entrega 2).

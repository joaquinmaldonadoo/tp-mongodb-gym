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

## Preparar Python (una sola vez)

```bash
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Cada vez que abras una terminal nueva, activá el entorno con `source .venv/bin/activate`.

## Cargar los datos de prueba

```bash
python scripts/seed.py
```

Borra la base `gym`, crea las colecciones con validación de esquema e inserta unos 485 documentos (6 planes, 92 clientes y ~390 asistencias). También los exporta a `data/*.json`. Se puede correr las veces que haga falta: siempre deja la base en el mismo estado inicial.

Los datos incluyen casos límite: clientes sin plan, sin email, con 0 cupos, con plan vencido, con plan libre (sin cupos), un DNI de 7 dígitos y un plan inactivo en el catálogo.

## Verificar los datos

```bash
python scripts/verificar.py
```

Chequea cantidades, DNI duplicados, asistencias huérfanas, que los cupos usados coincidan con las asistencias del período y que el validador rechace documentos inválidos.

## Consultas e índices

```bash
docker exec gym-mongo mongosh --quiet /queries/consultas.js
docker exec gym-mongo mongosh --quiet /queries/indices.js
```

- `queries/consultas.js`: las 10 consultas, cada una con su objetivo, el requerimiento que responde y el resultado esperado.
- `queries/indices.js`: crea los índices y compara cada consulta con y sin índice usando `explain("executionStats")`.

## Prueba de consistencia

```bash
python scripts/prueba_transaccion.py
```

Registra asistencias con una transacción multidocumento y prueba cuatro casos: normal, sin cupos, plan vencido y falla simulada en medio de la operación. Al final muestra qué pasaría sin transacción. Para volver al estado inicial, correr de nuevo `seed.py`.

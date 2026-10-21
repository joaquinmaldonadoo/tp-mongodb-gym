# TP Integrador MongoDB — Gestión de cupos y asistencias de un gimnasio

Base de Datos Aplicada · UCC · Ingeniería en Informática

Sistema que registra clientes de un gimnasio, sus planes por cupos y sus asistencias, descontando cupos de forma consistente. El diseño completo está en [docs/diseno.md](docs/diseno.md).

## Estructura del repo

```
docs/        Documento de diseño (entrega 1) e informe
data/        Datos de prueba (JSON)
scripts/     Scripts de creación y carga de la base
queries/     Las 10 consultas comentadas y los índices
api/         API con FastAPI (rutas, servicios y repositorios)
tests/       Tests automáticos de integración de la API
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

2. Iniciar MongoDB y la API:

   ```bash
   docker compose up -d --build
   ```

3. Verificar que estén funcionando (Mongo tiene que decir `healthy` después de unos segundos):

   ```bash
   docker compose ps
   ```

4. Conectarse desde Compass con:

   ```
   mongodb://localhost:27017/?directConnection=true
   ```

5. Abrir la documentación de la API (Swagger) en http://localhost:8000/docs

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

## API

La API corre como servicio del compose (`gym-api`) en http://localhost:8000. Swagger, en http://localhost:8000/docs, permite probar todos los endpoints desde el navegador.

| Método | Endpoint | Qué hace | Requerimiento |
| --- | --- | --- | --- |
| POST | `/clientes` | Crea un cliente | RF1 |
| GET | `/clientes` | Lista con filtros: `estado`, `plan`, `cupos_max`, `vigente`, `buscar`, `limite`, `salto` | RF1, RF5 |
| GET | `/clientes/{id}` | Obtiene un cliente | RF1 |
| PATCH | `/clientes/{id}` | Actualiza solo los campos enviados (`null` borra un campo opcional) | RF1 |
| DELETE | `/clientes/{id}` | Borra el cliente y sus asistencias (en una transacción) | RF1 |
| PUT | `/clientes/{id}/plan` | Asigna o renueva el plan (copia precio y cupos del catálogo) | RF2 |
| GET | `/clientes/{id}/asistencias` | Historial, del más reciente al más antiguo | RF6 |
| POST | `/asistencias` | Registra una asistencia y descuenta un cupo (en una transacción) | RF3, RF4 |
| GET | `/planes` | Catálogo de planes (para obtener el `plan_id`) | RF2 |
| GET | `/health` | Estado de la API y de la conexión a Mongo | — |

### Capas

```
api/app/
  routers/       reciben el pedido HTTP y arman la respuesta (no tocan Mongo)
  services/      reglas de negocio y transacciones
  repositories/  único lugar que accede a MongoDB
  schemas.py     validación de entrada y formato de salida (Pydantic)
  errores.py     errores del dominio, que main.py traduce a códigos HTTP
```

### Códigos de respuesta

| Código | Cuándo |
| --- | --- |
| 200 / 201 / 204 | Operación correcta (consulta, creación, borrado) |
| 400 | El ID no tiene formato de ObjectId |
| 404 | El cliente o el plan no existen |
| 409 | DNI repetido, cliente no activo, sin plan, plan vencido o sin cupos |
| 422 | Datos inválidos, campos desconocidos, plan discontinuado o actividad no incluida en el plan |
| 500 | Error inesperado (la transacción se aborta y no queda nada a medias) |
| 503 | No hay conexión con MongoDB |

### Correr la API sin Docker (opcional)

```bash
uvicorn app.main:app --app-dir api --reload
```

## Tests automáticos

Con Mongo levantado y el entorno de Python activo:

```bash
python -m pytest -v
```

Son 33 tests de integración que usan la API contra Mongo real, en una base aparte (`gym_test`) que se recarga antes de cada test, así que la base `gym` no se modifica. Cubren el CRUD completo, las validaciones y los códigos de error, la asignación de planes y el caso de consistencia, incluidas una falla simulada en medio de la transacción y una prueba de concurrencia (5 registros simultáneos del último cupo: solo uno tiene éxito).

## Análisis de datos

`analisis/analisis.ipynb` responde cuándo se llena el gym, si los planes están bien dimensionados y qué clientes hay que contactar. Los gráficos quedan guardados en `analisis/graficos/`.

Para abrirlo, usá VS Code (con la extensión Jupyter, eligiendo el kernel `.venv`) o corré:

```bash
jupyter notebook analisis/analisis.ipynb
```

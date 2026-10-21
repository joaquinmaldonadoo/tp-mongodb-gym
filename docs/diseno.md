# TP Integrador MongoDB — Diseño (Entrega 1)

## Problema

Un gimnasio vende planes con una cantidad fija de clases por mes (cupos) y necesita registrar cada asistencia y descontar el cupo correspondiente. Hoy ese control se hace a mano, así que hay errores (socios que asisten sin cupos, cupos que no se descuentan y planes vencidos que siguen activos).

El sistema guarda los clientes, sus planes y sus asistencias, descuenta cupos de forma consistente y permite analizar el uso del gimnasio (días y horarios pico, aprovechamiento de cada plan).

MongoDB encaja porque los planes y las actividades tienen atributos variables (un plan libre no tiene cupos, una clase puede tener coach o no) y porque el acceso principal es "traer un cliente con su plan actual", que se resuelve leyendo un solo documento.

## Actores y requerimientos

| Actor | Qué hace |
| --- | --- |
| Administrador | Gestiona planes y clientes, consulta reportes |
| Recepcionista | Da de alta clientes, registra asistencias |
| Cliente | Consulta sus cupos restantes y su historial (vía API) |

Requerimientos funcionales:

1. RF1: alta, consulta, modificación, baja y listado de clientes (CRUD de la entidad principal).
2. RF2: asignar o renovar un plan a un cliente, cargando sus cupos y su fecha de vencimiento.
3. RF3: registrar una asistencia y descontar un cupo en la misma operación.
4. RF4: rechazar la asistencia si el cliente no tiene cupos o tiene el plan vencido.
5. RF5: listar clientes filtrando por plan, estado o cupos restantes.
6. RF6: consultar el historial de asistencias de un cliente.
7. RF7: obtener reportes de asistencia por día, horario y actividad, y de uso de cada plan.

## Colecciones

El modelo usa tres colecciones. `clientes` es la entidad principal del CRUD.

| Colección | Qué guarda | Cantidad estimada de documentos |
| --- | --- | --- |
| `clientes` | Datos del socio + copia del plan vigente + cupos restantes | 80–100 |
| `planes` | Catálogo de planes (nombre, precio, cupos por mes) | 4–6 |
| `asistencias` | Una entrada por cada vez que un cliente asiste | 250–400 |

 
## Documentos de ejemplo

### clientes

```json
{
  "_id": ObjectId("6710a1..."),
  "dni": "42123456",
  "nombre": "Lucía",
  "apellido": "Gómez",
  "email": "lucia@mail.com",
  "telefono": "3515551234",
  "fecha_alta": ISODate("2026-03-02"),
  "estado": "activo",
  "plan_actual": {
    "plan_id": ObjectId("6710p1..."),
    "nombre": "12 clases",
    "precio_pagado": 38000,
    "cupos_totales": 12,
    "cupos_restantes": 7,
    "fecha_inicio": ISODate("2026-10-01"),
    "fecha_vencimiento": ISODate("2026-10-31")
  },
  "objetivos": ["fuerza", "hyrox"],
  "contacto_emergencia": { "nombre": "Marta Gómez", "telefono": "3515559999" }
}
```

- Obligatorios: `dni` (único), `nombre`, `apellido`, `estado`, `fecha_alta`.
- Opcionales: `email`, `telefono`, `objetivos`, `contacto_emergencia`, `plan_actual` (un cliente recién dado de alta puede no tener plan).
- Anidado: `plan_actual`, `contacto_emergencia`. Arreglo: `objetivos`.
- Caso límite: plan libre con `cupos_totales: null`, que no descuenta cupos.

### planes

```json
{
  "_id": ObjectId("6710p1..."),
  "nombre": "12 clases",
  "precio": 38000,
  "cupos_mensuales": 12,
  "duracion_dias": 30,
  "actividades_incluidas": ["crossfit", "funcional", "musculacion"],
  "activo": true
}
```

- Obligatorios: `nombre`, `precio`, `duracion_dias`, `activo`.
- Opcional: `cupos_mensuales` (no existe en el plan libre).

### asistencias

```json
{
  "_id": ObjectId("6711a9..."),
  "cliente_id": ObjectId("6710a1..."),
  "fecha_hora": ISODate("2026-10-14T19:05:00Z"),
  "actividad": "crossfit",
  "cupos_restantes_post": 7,
  "coach": "Nico"
}
```

- Obligatorios: `cliente_id`, `fecha_hora`, `actividad`.
- Opcional: `coach`. `cupos_restantes_post` guarda cuántos cupos le quedaron al cliente, para auditar.

## Relaciones: embeber o referenciar


| Relación | Decisión | Por qué |
| --- | --- | --- |
| Cliente → plan vigente | Embebido (`plan_actual`) como copia, más `plan_id` de referencia | Se lee en cada asistencia junto al cliente. La copia congela precio y cupos contratados aunque el plan cambie después. |
| Cliente → contacto de emergencia | Embebido | Pertenece a un solo cliente, es chico y nunca se consulta solo. |
| Cliente → asistencias | Referencia (`cliente_id` en `asistencias`) | Crecen sin límite mas o menos unas 150 por año por socio. Embebidas inflarían el documento y se consultan por fecha sin importar el cliente. |
| Plan → clientes | Sin enlace inverso | No hace falta porque "clientes de un plan" se resuelve filtrando por `plan_actual.plan_id`. |

 
## Consistencia, consultas e índices previstos

### Caso de consistencia: registrar asistencia

La operación inserta un documento en `asistencias` y resta 1 a `plan_actual.cupos_restantes` en `clientes`. Si solo se completa una de las dos partes, queda una asistencia sin cupo descontado (el cliente entrena gratis) o un cupo descontado sin asistencia (el cliente pierde una clase).

La solución es una transacción multidocumento. Dentro de ella se ejecuta un `updateOne` con la condición `cupos_restantes > 0` y plan no vencido. Si no modifica ningún documento, se aborta. Si sí lo modifica, se inserta la asistencia. Esto requiere levantar MongoDB como replica set de un nodo en Docker.

### Consultas previstas

|  | Tipo pedido | Pregunta del dominio |
| --- | --- | --- |
| 1 | Comparación | ¿Qué clientes tienen 2 cupos o menos? |
| 2 | Comparación | ¿Qué planes vencen en los próximos 7 días? |
| 3 | Lógicos | Clientes activos con plan de 12 clases o sin email cargado |
| 4 | Anidado | Clientes cuyo `plan_actual.nombre` es "8 clases" |
| 5 | Arreglo | Clientes con objetivo "hyrox" |
| 6 | Proyección + orden + límite | Los 10 últimos clientes dados de alta, solo nombre y fecha |
| 7 | Aggregate | Asistencias por día de la semana |
| 8 | Aggregate | Asistencias por actividad y franja horaria |
| 9 | Agrupamiento + estadística | Promedio, mínimo y máximo de cupos usados por plan |
| 10 | Libre | Ranking de clientes más constantes del mes con `$lookup` a `clientes` |

### Índices previstos

| Índice | Para qué consulta |
| --- | --- |
| `clientes.dni` (único) | Buscar un cliente en recepción y evitar duplicados |
| `asistencias { cliente_id: 1, fecha_hora: -1 }` | Historial de un cliente (RF6) y la transacción |
| `clientes.plan_actual.fecha_vencimiento` | Planes por vencer (consulta 2) |


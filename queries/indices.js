// =============================================================================
// Índices y análisis con explain("executionStats") — base `gym`
//
// Ejecutar (después de cargar los datos):
//   docker exec gym-mongo mongosh --quiet /queries/indices.js
//
// Para cada índice se corre la misma consulta dos veces:
//   - forzando un recorrido completo de la colección (hint({ $natural: 1 }))
//   - dejando que Mongo use el índice
// y se comparan los documentos examinados contra los devueltos.
// =============================================================================

db = db.getSiblingDB("gym");
const hoy = new Date();
const enDias = (n) => new Date(hoy.getTime() + n * 24 * 60 * 60 * 1000);


// --- Creación de índices -----------------------------------------------------

// 1. DNI único (ya lo crea seed.py; createIndex no falla si ya existe igual).
//    Recepción busca al cliente por DNI en cada asistencia y además no puede
//    haber dos clientes con el mismo DNI.
db.clientes.createIndex({ dni: 1 }, { unique: true, name: "dni_unico" });

// 2. Compuesto en asistencias: cliente + fecha descendente.
//    Sirve para el historial de un cliente (RF6), que filtra por cliente_id y
//    ordena por fecha. Como el orden del índice coincide con el del sort, Mongo
//    no necesita ordenar en memoria.
db.asistencias.createIndex({ cliente_id: 1, fecha_hora: -1 }, { name: "cliente_fecha" });

// 3. Fecha de vencimiento del plan (campo anidado).
//    Sirve para la consulta 2 (planes que vencen esta semana) y para la 1 y la 9,
//    que también filtran por planes vigentes.
db.clientes.createIndex({ "plan_actual.fecha_vencimiento": 1 }, { name: "vencimiento_plan" });

print("Índices de clientes:");
db.clientes.getIndexes().forEach((i) => print(`  ${i.name}: ${JSON.stringify(i.key)}`));
print("Índices de asistencias:");
db.asistencias.getIndexes().forEach((i) => print(`  ${i.name}: ${JSON.stringify(i.key)}`));


// --- Utilidades para leer el explain -----------------------------------------

function etapas(plan) {
  // Recorre el árbol del plan ganador y devuelve las etapas, de afuera hacia adentro
  if (!plan) return [];
  const actual = plan.stage + (plan.indexName ? `(${plan.indexName})` : "");
  const hijos = plan.inputStage ? [plan.inputStage] : (plan.inputStages || []);
  return [actual, ...hijos.flatMap(etapas)];
}

function resumen(titulo, explain) {
  const s = explain.executionStats;
  const ganador = explain.queryPlanner.winningPlan.queryPlan || explain.queryPlanner.winningPlan;
  print(`\n  ${titulo}`);
  print(`    Plan:                 ${etapas(ganador).join(" <- ")}`);
  print(`    Documentos devueltos: ${s.nReturned}`);
  print(`    Claves examinadas:    ${s.totalKeysExamined}`);
  print(`    Documentos leídos:    ${s.totalDocsExamined}`);
  print(`    Tiempo (ms):          ${s.executionTimeMillis}`);
}

function comparar(titulo, consulta) {
  print(`\n=== ${titulo} ===`);
  resumen("Sin índice (recorrido completo):", consulta().hint({ $natural: 1 }).explain("executionStats"));
  resumen("Con índice:", consulta().explain("executionStats"));
}


// --- Análisis -----------------------------------------------------------------

// Índice 1: buscar un cliente por DNI
const unCliente = db.clientes.findOne({ "plan_actual.cupos_restantes": { $gt: 3 } });
comparar(`Buscar cliente por DNI (${unCliente.dni})`,
  () => db.clientes.find({ dni: unCliente.dni }));

// Índice 2: historial de asistencias del cliente que más fue
const masConstante = db.asistencias.aggregate([
  { $group: { _id: "$cliente_id", n: { $sum: 1 } } }, { $sort: { n: -1 } }, { $limit: 1 },
]).next();
comparar("Historial de asistencias de un cliente, más reciente primero",
  () => db.asistencias.find({ cliente_id: masConstante._id }).sort({ fecha_hora: -1 }));

// Índice 3: planes que vencen en los próximos 7 días (consulta 2)
comparar("Planes que vencen en los próximos 7 días",
  () => db.clientes.find({ "plan_actual.fecha_vencimiento": { $gte: hoy, $lte: enDias(7) } }));


// --- Costo de los índices -----------------------------------------------------

print("\n=== Tamaño de los índices (bytes) ===");
printjson({ clientes: db.clientes.stats().indexSizes, asistencias: db.asistencias.stats().indexSizes });
print(
  "\nCada índice ocupa espacio y hace más lentas las escrituras, porque cada insert o update\n" +
  "también actualiza el índice. Por eso no se indexan campos como 'objetivos' o 'actividad':\n" +
  "tienen pocos valores distintos y se consultan poco, así que el índice no ahorraría casi nada."
);

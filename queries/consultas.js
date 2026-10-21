// =============================================================================
// Consultas del TP — base `gym`
//
// Ejecutar (con Mongo levantado y los datos cargados):
//   docker exec gym-mongo mongosh --quiet /queries/consultas.js
//
// Cada consulta indica: el tipo que pide la consigna, la pregunta del dominio
// que responde, el requerimiento funcional asociado y el resultado esperado.
// Las fechas son relativas a "hoy" porque los datos de prueba también lo son.
// =============================================================================

db = db.getSiblingDB("gym");

const hoy = new Date();
const enDias = (n) => new Date(hoy.getTime() + n * 24 * 60 * 60 * 1000);
const TZ = "America/Argentina/Cordoba";

function mostrar(numero, titulo, resultado) {
  const docs = Array.isArray(resultado) ? resultado : resultado.toArray();
  print(`\n=== Consulta ${numero}: ${titulo} (${docs.length} resultados) ===`);
  docs.forEach((d) => printjson(d));
}


// -----------------------------------------------------------------------------
// 1. Filtro con operadores de comparación
// Pregunta: ¿Qué clientes con plan vigente tienen 2 cupos o menos?
//           Sirve para avisarles que renueven antes de quedarse sin clases.
// RF5. Resultado esperado: clientes con cupos_restantes entre 0 y 2 y
//      vencimiento posterior a hoy. Los planes libres (cupos null) no aparecen,
//      porque $lte solo compara contra números.
// -----------------------------------------------------------------------------
mostrar(1, "Clientes con 2 cupos o menos",
  db.clientes.find(
    {
      "plan_actual.cupos_restantes": { $lte: 2 },
      "plan_actual.fecha_vencimiento": { $gte: hoy },
    },
    { _id: 0, dni: 1, nombre: 1, apellido: 1, telefono: 1,
      "plan_actual.nombre": 1, "plan_actual.cupos_restantes": 1 }
  ).sort({ "plan_actual.cupos_restantes": 1 })
);


// -----------------------------------------------------------------------------
// 2. Filtro con operadores de comparación (rango de fechas)
// Pregunta: ¿A qué clientes se les vence el plan en los próximos 7 días?
//           Es la lista de cobranza de la semana.
// RF2. Resultado esperado: clientes con fecha_vencimiento entre hoy y hoy+7,
//      ordenados por el que vence primero.
// -----------------------------------------------------------------------------
mostrar(2, "Planes que vencen en los próximos 7 días",
  db.clientes.find(
    { "plan_actual.fecha_vencimiento": { $gte: hoy, $lte: enDias(7) } },
    { _id: 0, nombre: 1, apellido: 1, email: 1,
      "plan_actual.nombre": 1, "plan_actual.fecha_vencimiento": 1 }
  ).sort({ "plan_actual.fecha_vencimiento": 1 })
);


// -----------------------------------------------------------------------------
// 3. Operadores lógicos ($and, $or, $exists)
// Pregunta: ¿Qué clientes activos tienen plan de 12 clases, o no tienen email
//           cargado? Recepción los contacta para ofrecerles el plan de 16
//           (a los primeros) o para completar sus datos (a los segundos).
// RF5. Resultado esperado: solo clientes con estado "activo" que cumplen al
//      menos una de las dos condiciones.
// -----------------------------------------------------------------------------
mostrar(3, "Activos con plan de 12 clases o sin email",
  db.clientes.find(
    {
      $and: [
        { estado: "activo" },
        { $or: [
          { "plan_actual.nombre": "12 clases" },
          { email: { $exists: false } },
        ] },
      ],
    },
    { _id: 0, nombre: 1, apellido: 1, email: 1, "plan_actual.nombre": 1 }
  )
);


// -----------------------------------------------------------------------------
// 4. Consulta sobre atributos anidados
// Pregunta: ¿Qué clientes del plan "8 clases" ya usaron la mitad o más de sus
//           cupos y tienen contacto de emergencia cargado?
//           Son candidatos a pasarse a un plan más grande.
// RF5. Resultado esperado: filtra por tres campos de subdocumentos
//      (plan_actual.nombre, plan_actual.cupos_restantes, contacto_emergencia).
// -----------------------------------------------------------------------------
mostrar(4, "Plan 8 clases con la mitad de los cupos usados",
  db.clientes.find(
    {
      "plan_actual.nombre": "8 clases",
      "plan_actual.cupos_restantes": { $lte: 4 },
      "plan_actual.fecha_vencimiento": { $gte: hoy },
      "contacto_emergencia.telefono": { $exists: true },
    },
    { _id: 0, nombre: 1, apellido: 1, plan_actual: 1, "contacto_emergencia.nombre": 1 }
  )
);


// -----------------------------------------------------------------------------
// 5. Consulta sobre arreglos
// Pregunta: ¿Qué clientes tienen "hyrox" entre sus objetivos? Y de esos,
//           ¿quiénes además buscan "fuerza"? Sirve para armar el grupo de
//           entrenamiento para la próxima competencia.
// Resultado esperado: la primera busca un elemento dentro del arreglo;
//      la segunda usa $all (tiene que contener ambos valores, en cualquier orden).
// -----------------------------------------------------------------------------
mostrar("5a", "Clientes con objetivo hyrox",
  db.clientes.find({ objetivos: "hyrox" }, { _id: 0, nombre: 1, apellido: 1, objetivos: 1 })
);
mostrar("5b", "Clientes con objetivos hyrox y fuerza",
  db.clientes.find({ objetivos: { $all: ["hyrox", "fuerza"] } },
                   { _id: 0, nombre: 1, apellido: 1, objetivos: 1 })
);


// -----------------------------------------------------------------------------
// 6. Proyección, ordenamiento y límite
// Pregunta: ¿Quiénes son los 10 últimos clientes dados de alta?
//           Para hacerles el seguimiento de bienvenida.
// RF1. Resultado esperado: 10 documentos con solo nombre, apellido y
//      fecha_alta, del más reciente al más antiguo.
// -----------------------------------------------------------------------------
mostrar(6, "Últimas 10 altas",
  db.clientes.find({}, { _id: 0, nombre: 1, apellido: 1, fecha_alta: 1 })
    .sort({ fecha_alta: -1 })
    .limit(10)
);


// -----------------------------------------------------------------------------
// 7. Pipeline de agregación
// Pregunta: ¿Qué días de la semana va más gente?
// RF7. Resultado esperado: un documento por día con la cantidad de
//      asistencias, de mayor a menor. El día se calcula en hora de Córdoba,
//      porque Mongo guarda las fechas en UTC.
// -----------------------------------------------------------------------------
mostrar(7, "Asistencias por día de la semana",
  db.asistencias.aggregate([
    { $group: {
      _id: { $dayOfWeek: { date: "$fecha_hora", timezone: TZ } },  // 1 = domingo ... 7 = sábado
      asistencias: { $sum: 1 },
    } },
    { $project: {
      _id: 0,
      dia: { $arrayElemAt: [
        ["", "Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"], "$_id"] },
      asistencias: 1,
    } },
    { $sort: { asistencias: -1 } },
  ])
);


// -----------------------------------------------------------------------------
// 8. Pipeline de agregación
// Pregunta: ¿Qué actividades se llenan en cada franja horaria?
//           Ayuda a decidir dónde agregar turnos o coaches.
// RF7. Resultado esperado: combinaciones actividad + franja con su cantidad
//      de asistencias, de mayor a menor.
// -----------------------------------------------------------------------------
mostrar(8, "Asistencias por actividad y franja horaria",
  db.asistencias.aggregate([
    { $addFields: { hora: { $hour: { date: "$fecha_hora", timezone: TZ } } } },
    { $addFields: { franja: { $switch: {
      branches: [
        { case: { $lt: ["$hora", 12] }, then: "mañana (7-11)" },
        { case: { $lt: ["$hora", 17] }, then: "mediodía (12-16)" },
      ],
      default: "tarde-noche (17-21)",
    } } } },
    { $group: { _id: { actividad: "$actividad", franja: "$franja" }, asistencias: { $sum: 1 } } },
    { $project: { _id: 0, actividad: "$_id.actividad", franja: "$_id.franja", asistencias: 1 } },
    { $sort: { asistencias: -1 } },
  ])
);


// -----------------------------------------------------------------------------
// 9. Agrupamiento con cálculos estadísticos
// Pregunta: En los planes vigentes con cupos, ¿cuántos cupos se usan en
//           promedio, como mínimo y como máximo? ¿Qué porcentaje del plan se
//           aprovecha? Muestra si un plan está sobredimensionado.
// RF7. Resultado esperado: un documento por plan con cantidad de clientes,
//      promedio, mínimo, máximo y porcentaje promedio de uso.
// -----------------------------------------------------------------------------
mostrar(9, "Uso de cupos por plan",
  db.clientes.aggregate([
    { $match: {
      "plan_actual.cupos_totales": { $ne: null },
      "plan_actual.fecha_vencimiento": { $gte: hoy },
    } },
    { $addFields: {
      usados: { $subtract: ["$plan_actual.cupos_totales", "$plan_actual.cupos_restantes"] },
    } },
    { $group: {
      _id: "$plan_actual.nombre",
      clientes: { $sum: 1 },
      promedio_usados: { $avg: "$usados" },
      minimo_usados: { $min: "$usados" },
      maximo_usados: { $max: "$usados" },
      cupos_del_plan: { $first: "$plan_actual.cupos_totales" },
      uso_promedio: { $avg: { $divide: ["$usados", "$plan_actual.cupos_totales"] } },
    } },
    { $project: {
      _id: 0, plan: "$_id", clientes: 1, cupos_del_plan: 1, minimo_usados: 1, maximo_usados: 1,
      promedio_usados: { $round: ["$promedio_usados", 1] },
      porcentaje_uso: { $round: [{ $multiply: ["$uso_promedio", 100] }, 1] },
    } },
    { $sort: { porcentaje_uso: -1 } },
  ])
);


// -----------------------------------------------------------------------------
// 10. Consulta adicional: ranking con $lookup entre colecciones
// Pregunta: ¿Quiénes son los 10 clientes más constantes de los últimos 30 días?
//           Para un sorteo o reconocimiento mensual.
// RF6/RF7. Resultado esperado: 10 clientes con su cantidad de asistencias y la
//      última vez que fueron. Une asistencias con clientes, ya que la asistencia
//      solo guarda el cliente_id (referencia).
// -----------------------------------------------------------------------------
mostrar(10, "Ranking de constancia de los últimos 30 días",
  db.asistencias.aggregate([
    { $match: { fecha_hora: { $gte: enDias(-30) } } },
    { $group: {
      _id: "$cliente_id",
      asistencias: { $sum: 1 },
      ultima_vez: { $max: "$fecha_hora" },
      actividades: { $addToSet: "$actividad" },
    } },
    { $sort: { asistencias: -1, ultima_vez: -1 } },
    { $limit: 10 },
    { $lookup: { from: "clientes", localField: "_id", foreignField: "_id", as: "cliente" } },
    { $unwind: "$cliente" },
    { $project: {
      _id: 0,
      cliente: { $concat: ["$cliente.nombre", " ", "$cliente.apellido"] },
      plan: "$cliente.plan_actual.nombre",
      asistencias: 1, ultima_vez: 1, actividades: 1,
    } },
  ])
);

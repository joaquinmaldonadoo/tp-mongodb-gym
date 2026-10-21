"""Tests del CRUD de clientes y de la asignación de planes."""

NUEVO = {
    "dni": "44555666",
    "nombre": "Joaquín",
    "apellido": "Maldonado",
    "email": "joaquin@mail.com",
    "objetivos": ["Hyrox", "fuerza", "hyrox"],
}


def crear(api, **cambios):
    respuesta = api.post("/clientes", json={**NUEVO, **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- POST /clientes --------------------------------------------------------------

def test_crear_cliente(api, db):
    cliente = crear(api)
    assert cliente["dni"] == "44555666"
    assert cliente["estado"] == "activo"
    assert cliente["objetivos"] == ["hyrox", "fuerza"]  # normalizados y sin repetidos
    assert cliente["plan_actual"] is None
    assert db.clientes.count_documents({"dni": "44555666"}) == 1


def test_crear_con_dni_repetido_da_409(api):
    crear(api)
    respuesta = api.post("/clientes", json={**NUEVO, "nombre": "Otro"})
    assert respuesta.status_code == 409
    assert "DNI" in respuesta.json()["detalle"]


def test_crear_con_datos_invalidos_da_422(api):
    respuesta = api.post("/clientes", json={"dni": "12ab", "nombre": "", "apellido": "X",
                                            "email": "sin-arroba", "cupos_restantes": 99})
    assert respuesta.status_code == 422
    campos = {e["campo"] for e in respuesta.json()["errores"]}
    assert {"dni", "nombre", "email", "cupos_restantes"} <= campos


def test_crear_sin_campos_obligatorios_da_422(api):
    assert api.post("/clientes", json={"nombre": "Solo nombre"}).status_code == 422


# --- GET /clientes/{id} ----------------------------------------------------------

def test_obtener_cliente(api):
    creado = crear(api)
    respuesta = api.get(f"/clientes/{creado['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Joaquín"


def test_obtener_id_inexistente_da_404(api):
    assert api.get("/clientes/6710a1b2c3d4e5f6a7b8c9d0").status_code == 404


def test_obtener_id_mal_formado_da_400(api):
    assert api.get("/clientes/no-es-un-id").status_code == 400


# --- GET /clientes ---------------------------------------------------------------

def test_listar_con_paginacion(api, db):
    respuesta = api.get("/clientes?limite=10&salto=0").json()
    assert respuesta["total"] == db.clientes.count_documents({})
    assert len(respuesta["resultados"]) == 10
    siguiente = api.get("/clientes?limite=10&salto=10").json()["resultados"]
    assert {c["id"] for c in respuesta["resultados"]}.isdisjoint({c["id"] for c in siguiente})


def test_listar_filtra_por_estado_y_cupos(api):
    inactivos = api.get("/clientes?estado=inactivo").json()
    assert inactivos["total"] > 0
    assert all(c["estado"] == "inactivo" for c in inactivos["resultados"])

    pocos = api.get("/clientes?cupos_max=1&vigente=true&limite=100").json()["resultados"]
    assert pocos and all(c["plan_actual"]["cupos_restantes"] <= 1 for c in pocos)


def test_listar_buscar_por_texto(api):
    crear(api)
    resultados = api.get("/clientes?buscar=maldo").json()["resultados"]
    assert [c["dni"] for c in resultados] == ["44555666"]


def test_listar_parametro_invalido_da_422(api):
    assert api.get("/clientes?limite=0").status_code == 422
    assert api.get("/clientes?estado=borrado").status_code == 422


# --- PATCH /clientes/{id} --------------------------------------------------------

def test_actualizar_y_borrar_campo_opcional(api, db):
    creado = crear(api)
    respuesta = api.patch(f"/clientes/{creado['id']}", json={"telefono": "3517778888", "email": None})
    assert respuesta.status_code == 200
    assert respuesta.json()["telefono"] == "3517778888"
    documento = db.clientes.find_one({"dni": "44555666"})
    assert "email" not in documento  # null borra el campo del documento


def test_actualizar_no_permite_borrar_obligatorios(api):
    creado = crear(api)
    assert api.patch(f"/clientes/{creado['id']}", json={"dni": None}).status_code == 422


def test_actualizar_sin_campos_da_422(api):
    creado = crear(api)
    assert api.patch(f"/clientes/{creado['id']}", json={}).status_code == 422


def test_actualizar_no_permite_tocar_el_plan(api):
    creado = crear(api)
    respuesta = api.patch(f"/clientes/{creado['id']}", json={"plan_actual": {"cupos_restantes": 99}})
    assert respuesta.status_code == 422


def test_actualizar_con_dni_de_otro_cliente_da_409(api, buscar_cliente):
    creado = crear(api)
    otro = buscar_cliente()
    assert api.patch(f"/clientes/{creado['id']}", json={"dni": otro["dni"]}).status_code == 409


def test_actualizar_inexistente_da_404(api):
    assert api.patch("/clientes/6710a1b2c3d4e5f6a7b8c9d0", json={"nombre": "X"}).status_code == 404


# --- DELETE /clientes/{id} -------------------------------------------------------

def test_eliminar_borra_cliente_y_asistencias(api, db, buscar_cliente):
    cliente = buscar_cliente()
    assert db.asistencias.count_documents({"cliente_id": cliente["_id"]}) > 0

    assert api.delete(f"/clientes/{cliente['_id']}").status_code == 204
    assert api.get(f"/clientes/{cliente['_id']}").status_code == 404
    assert db.asistencias.count_documents({"cliente_id": cliente["_id"]}) == 0


def test_eliminar_inexistente_da_404(api):
    assert api.delete("/clientes/6710a1b2c3d4e5f6a7b8c9d0").status_code == 404


# --- PUT /clientes/{id}/plan -----------------------------------------------------

def plan_por_nombre(db, nombre):
    return db.planes.find_one({"nombre": nombre})


def test_asignar_plan_copia_precio_y_cupos(api, db):
    creado = crear(api)
    plan = plan_por_nombre(db, "12 clases")
    respuesta = api.put(f"/clientes/{creado['id']}/plan", json={"plan_id": str(plan["_id"])})
    assert respuesta.status_code == 200
    actual = respuesta.json()["plan_actual"]
    assert actual["nombre"] == "12 clases"
    assert actual["cupos_totales"] == actual["cupos_restantes"] == 12
    assert actual["precio_pagado"] == plan["precio"]


def test_asignar_plan_discontinuado_da_422(api, db):
    creado = crear(api)
    plan = plan_por_nombre(db, "4 clases")
    assert api.put(f"/clientes/{creado['id']}/plan", json={"plan_id": str(plan["_id"])}).status_code == 422


def test_asignar_plan_inexistente_da_404(api):
    creado = crear(api)
    assert api.put(f"/clientes/{creado['id']}/plan", json={"plan_id": "6710a1b2c3d4e5f6a7b8c9d0"}).status_code == 404


def test_asignar_plan_a_cliente_inactivo_da_409(api, db, buscar_cliente):
    inactivo = buscar_cliente(tipo="inactivo")
    plan = plan_por_nombre(db, "8 clases")
    assert api.put(f"/clientes/{inactivo['_id']}/plan", json={"plan_id": str(plan["_id"])}).status_code == 409


# --- GET /clientes/{id}/asistencias ----------------------------------------------

def test_historial_ordenado_del_mas_reciente(api, buscar_cliente):
    cliente = buscar_cliente()
    historial = api.get(f"/clientes/{cliente['_id']}/asistencias").json()
    fechas = [a["fecha_hora"] for a in historial]
    assert fechas and fechas == sorted(fechas, reverse=True)
    assert all(a["cliente_id"] == str(cliente["_id"]) for a in historial)

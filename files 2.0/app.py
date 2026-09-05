"""
app.py — Sistema de Control Avícola
------------------------------------------------------------
Script principal. Ejecutar con:

    streamlit run app.py

Integra:
    - database.py    -> persistencia SQLite (producción, ventas, gastos, precios)
    - calculadora.py  -> clasificación NTC 1240, conversión a cubetas y POS

Módulos de la interfaz (barra lateral):
    1. Dashboard              - resumen general del negocio
    2. Registrar Producción   - captura diaria de postura por galpón
    3. Clasificador NTC 1240  - clasifica un huevo (o un lote) por peso en gramos
    4. Punto de Venta (POS)   - calculadora de precios ágil y registro de ventas
    5. Inventario             - stock disponible por tipo de huevo
    6. Gastos                 - registro de egresos
    7. Configurar Precios     - tabla de precios por tipo y presentación

Notas de esta versión:
    - Se reemplazó el parámetro obsoleto `use_container_width` por `width`
      ("stretch" / "content"), siguiendo la guía oficial de deprecación de
      Streamlit.
    - El clasificador NTC 1240 ahora admite lotes completos de pesos
      (varios huevos a la vez) con resumen estadístico.
    - El módulo de ventas se rediseñó para calcular el total en vivo
      (sin botón intermedio de "calcular") y registrar la venta con un
      único clic, manteniendo un historial de la sesión en
      `st.session_state` además del historial persistido en SQLite.
------------------------------------------------------------
"""

from datetime import date

import pandas as pd
import streamlit as st

import database as db
import calculadora as calc

# ------------------------------------------------------------------
# Configuración general de la página
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Control Avícola",
    page_icon="🥚",
    layout="wide",
)

db.init_db()  # crea/asegura el esquema y las semillas al arrancar

# Etiquetas amigables para las presentaciones más usadas en el mostrador.
ETIQUETAS_PRESENTACION = {
    30: "Cubeta completa (30 u.)",
    20: "Paquete de 20 u.",
    15: "Cartón (15 u.)",
    12: "Cartón (12 u.)",
    10: "Paquete de 10 u.",
    6: "Media docena (6 u.)",
    1: "Unidad suelta",
}


def formato_cop(valor: float) -> str:
    """Formatea un número como pesos colombianos, ej. 15000 -> '$ 15.000'."""
    return f"$ {valor:,.0f}".replace(",", ".")


def etiqueta_presentacion(p: int) -> str:
    return ETIQUETAS_PRESENTACION.get(p, f"{p} u.")


# ------------------------------------------------------------------
# Estado de sesión (inicialización centralizada para evitar errores
# de "key not found" al navegar entre secciones)
# ------------------------------------------------------------------
if "ventas_sesion" not in st.session_state:
    st.session_state["ventas_sesion"] = []  # historial de ventas registradas en esta sesión


# ------------------------------------------------------------------
# Navegación
# ------------------------------------------------------------------
st.sidebar.title("🐔 Control Avícola")
seccion = st.sidebar.radio(
    "Menú",
    [
        "📊 Dashboard",
        "🥚 Registrar Producción",
        "⚖️ Clasificador NTC 1240",
        "🧮 Punto de Venta (POS)",
        "📦 Inventario",
        "💸 Gastos",
        "⚙️ Configurar Precios",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Clasificación de huevos según NTC 1240 (Icontec). "
    "Cubeta estándar = 30 unidades."
)


# ==================================================================
# 1. DASHBOARD
# ==================================================================
if seccion == "📊 Dashboard":
    st.title("Panel de Control de Gestión Avícola")

    resumen = db.obtener_resumen_dashboard()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Ingresos", formato_cop(resumen["total_ingresos"]))
    c2.metric("Total Gastos", formato_cop(resumen["total_gastos"]))
    c3.metric("Ganancia Neta", formato_cop(resumen["ganancia_neta"]))
    c4.metric("Huevos Producidos", f"{resumen['total_huevos_producidos']:,}".replace(",", "."))

    st.markdown("---")
    st.subheader("Inventario por tipo de huevo")
    inventario = calc.resumen_inventario_en_cubetas()
    df_inv = pd.DataFrame(inventario)
    if not df_inv.empty:
        df_inv_mostrar = df_inv.rename(
            columns={
                "tipo_huevo": "Tipo",
                "entradas_producidas": "Entradas (u.)",
                "salidas_vendidas": "Salidas (u.)",
                "stock_disponible": "Stock (u.)",
                "equivalencia_cubetas": "Equivalencia",
                "precio_ref_unidad": "Precio ref./u.",
                "valor_inventario_estimado": "Valor estimado",
            }
        )
        st.dataframe(
            df_inv_mostrar[
                ["Tipo", "Entradas (u.)", "Salidas (u.)", "Stock (u.)",
                 "Equivalencia", "Precio ref./u.", "Valor estimado"]
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            f"Valor total estimado del inventario: "
            f"{formato_cop(df_inv['valor_inventario_estimado'].sum())}"
        )


# ==================================================================
# 2. REGISTRAR PRODUCCIÓN
# ==================================================================
elif seccion == "🥚 Registrar Producción":
    st.title("Registrar Producción Diaria")

    with st.form("form_produccion", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=date.today())
            galpon = st.text_input("Galpón", placeholder="Galpón 1")
            tipo_huevo = st.selectbox("Tipo de huevo (clasificación predominante)", db.TIPOS_HUEVO)
        with col2:
            aves_iniciales = st.number_input("Aves vivas", min_value=0, step=1)
            mortalidad = st.number_input("Mortalidad del día", min_value=0, step=1)
            huevos_recogidos = st.number_input("Huevos recogidos", min_value=0, step=1)
            huevos_rotos = st.number_input("Huevos rotos/descartados", min_value=0, step=1)

        enviado = st.form_submit_button("Guardar registro")
        if enviado:
            if not galpon.strip():
                st.error("Debes indicar el nombre del galpón.")
            else:
                db.registrar_produccion(
                    fecha, galpon.strip(), tipo_huevo, aves_iniciales,
                    mortalidad, huevos_recogidos, huevos_rotos,
                )
                st.success(
                    f"Producción registrada: {huevos_recogidos} huevos "
                    f"({tipo_huevo}) en {galpon.strip()}."
                )

    st.markdown("---")
    st.subheader("Historial de producción")
    registros = db.obtener_produccion()
    if registros:
        st.dataframe(pd.DataFrame(registros), width="stretch", hide_index=True)
    else:
        st.info("Aún no hay registros de producción.")


# ==================================================================
# 3. CLASIFICADOR NTC 1240 (individual + lote)
# ==================================================================
elif seccion == "⚖️ Clasificador NTC 1240":
    st.title("Clasificador de Huevos — NTC 1240")

    modo_clasif = st.radio(
        "Modo de clasificación",
        ["Un solo huevo", "Lote de huevos (varios pesos a la vez)"],
        horizontal=True,
    )

    # ---------------- Modo: un solo huevo ----------------
    if modo_clasif == "Un solo huevo":
        st.write(
            "Ingresa el peso de un huevo en gramos para determinar su "
            "clasificación oficial según la norma técnica colombiana NTC 1240."
        )
        peso = st.number_input("Peso del huevo (gramos)", min_value=0.0, step=0.1, format="%.1f")
        if st.button("Clasificar"):
            try:
                tipo = calc.clasificar_huevo_por_peso(peso)
                st.success(f"Un huevo de **{peso} g** se clasifica como **{tipo}**.")
            except calc.PesoFueraDeRangoError as e:
                st.error(str(e))

    # ---------------- Modo: lote de huevos ----------------
    else:
        st.write(
            "Pega o escribe los pesos (en gramos) separados por coma, espacio "
            "o salto de línea. Ejemplo: `62, 58, 70, 45, 80, 66`"
        )
        texto_pesos = st.text_area(
            "Pesos del lote (gramos)",
            height=120,
            placeholder="62, 58, 70, 45, 80, 66, 53, 61 ...",
        )

        if st.button("Clasificar lote"):
            # Acepta comas, espacios y saltos de línea como separadores.
            crudos = texto_pesos.replace(",", " ").replace("\n", " ").split()
            pesos_validos, pesos_invalidos = [], []
            for token in crudos:
                try:
                    pesos_validos.append(float(token))
                except ValueError:
                    pesos_invalidos.append(token)

            if not pesos_validos:
                st.error("No se detectaron pesos válidos. Verifica el formato ingresado.")
            else:
                filas = []
                for peso in pesos_validos:
                    try:
                        tipo = calc.clasificar_huevo_por_peso(peso)
                    except calc.PesoFueraDeRangoError:
                        tipo = "No clasificable"
                    filas.append({"Peso (g)": peso, "Clasificación": tipo})

                df_lote = pd.DataFrame(filas)
                st.session_state["lote_clasificado"] = df_lote

                if pesos_invalidos:
                    st.warning(
                        f"Se ignoraron {len(pesos_invalidos)} valor(es) no numérico(s): "
                        f"{', '.join(pesos_invalidos)}"
                    )

        # Muestra resultados si ya se clasificó un lote en esta sesión
        if "lote_clasificado" in st.session_state:
            df_lote = st.session_state["lote_clasificado"]
            clasificables = df_lote[df_lote["Clasificación"] != "No clasificable"]

            st.markdown("---")
            st.subheader("Resumen estadístico del lote")

            c1, c2, c3 = st.columns(3)
            c1.metric("Total de huevos", len(df_lote))
            c2.metric(
                "Peso promedio",
                f"{clasificables['Peso (g)'].mean():.1f} g" if not clasificables.empty else "N/A",
            )
            c3.metric(
                "No clasificables",
                int((df_lote["Clasificación"] == "No clasificable").sum()),
            )

            st.markdown("##### Conteo por categoría (NTC 1240)")
            orden_categorias = db.TIPOS_HUEVO + ["No clasificable"]
            conteo = (
                clasificables["Clasificación"]
                .value_counts()
                .reindex(db.TIPOS_HUEVO, fill_value=0)
            )
            cols_conteo = st.columns(len(db.TIPOS_HUEVO))
            for i, tipo in enumerate(db.TIPOS_HUEVO):
                cols_conteo[i].metric(tipo, int(conteo.get(tipo, 0)))

            st.bar_chart(conteo)

            st.markdown("##### Detalle huevo por huevo")
            st.dataframe(df_lote, width="stretch", hide_index=True)

    st.markdown("---")
    st.subheader("Tabla de referencia NTC 1240")
    rangos = db.obtener_clasificacion_ntc1240()
    df_rangos = pd.DataFrame(rangos).rename(
        columns={"tipo_huevo": "Tipo", "peso_min_g": "Peso mín. (g)", "peso_max_g": "Peso máx. (g)"}
    )
    df_rangos["Peso máx. (g)"] = df_rangos["Peso máx. (g)"].fillna("En adelante")
    st.dataframe(df_rangos, width="stretch", hide_index=True)


# ==================================================================
# 4. PUNTO DE VENTA (POS) — flujo optimizado
# ==================================================================
elif seccion == "🧮 Punto de Venta (POS)":
    st.title("Calculadora de Precios / Punto de Venta")
    st.caption("El total se calcula automáticamente al cambiar cualquier campo.")

    precios = db.obtener_precios()

    col_izq, col_der = st.columns([1.1, 1])

    # ---------------- Columna izquierda: selección y cálculo en vivo ----------------
    with col_izq:
        tipo_huevo = st.selectbox("Tipo de huevo", db.TIPOS_HUEVO, key="pos_tipo")

        modo = st.radio(
            "¿Cómo quieres cobrar?",
            ["Por presentación (cubeta, cartón, unidad...)", "Por cantidad total de unidades"],
            key="pos_modo",
        )

        resultado = None

        if modo == "Por presentación (cubeta, cartón, unidad...)":
            presentaciones_disp = sorted(precios.get(tipo_huevo, {}).keys(), reverse=True)
            presentacion = st.selectbox(
                "Presentación",
                presentaciones_disp,
                format_func=etiqueta_presentacion,
                key="pos_presentacion",
            )
            cantidad = st.number_input(
                "Cantidad de paquetes", min_value=1, step=1, value=1, key="pos_cantidad_paq"
            )
            # Cálculo en vivo, sin botón intermedio.
            try:
                resultado = calc.calcular_precio_por_presentacion(tipo_huevo, presentacion, cantidad)
            except ValueError as e:
                st.error(str(e))

        else:
            unidades = st.number_input(
                "Total de unidades a vender", min_value=1, step=1, value=30, key="pos_unidades"
            )
            conv = calc.convertir_unidades_a_cubetas(unidades)
            st.caption(f"Equivalencia: {conv['descripcion']}")
            try:
                resultado = calc.calcular_precio_dinamico(tipo_huevo, unidades)
            except ValueError as e:
                st.error(str(e))

        cliente = st.text_input("Cliente", placeholder="Nombre del cliente", key="pos_cliente")
        fecha_venta = st.date_input("Fecha de venta", value=date.today(), key="pos_fecha")

    # ---------------- Columna derecha: resumen y confirmación ----------------
    with col_der:
        st.markdown("#### Resumen de la venta")
        if resultado is None:
            st.info("Completa los datos a la izquierda para ver el total.")
        else:
            filas = [
                {
                    "Presentación": etiqueta_presentacion(it.presentacion),
                    "Cantidad": it.cantidad_paquetes,
                    "Precio paquete": formato_cop(it.precio_unitario_paquete),
                    "Subtotal": formato_cop(it.subtotal),
                }
                for it in resultado.items
            ]
            st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)
            st.metric("Total a cobrar", formato_cop(resultado.total))
            st.caption(
                f"Unidades cubiertas: {resultado.unidades_cubiertas} · "
                f"Precio promedio/u.: {formato_cop(resultado.precio_promedio_unidad)}"
            )

            registrar_disabled = not cliente.strip()
            if registrar_disabled:
                st.caption("⚠️ Indica el nombre del cliente para poder registrar la venta.")

            if st.button("✅ Registrar venta", disabled=registrar_disabled, width="stretch"):
                primer_item = resultado.items[0] if len(resultado.items) == 1 else None
                db.registrar_venta(
                    fecha_venta,
                    cliente.strip(),
                    resultado.tipo_huevo,
                    resultado.unidades_cubiertas,
                    resultado.total,
                    presentacion=primer_item.presentacion if primer_item else None,
                    cantidad_paquetes=primer_item.cantidad_paquetes if primer_item else None,
                    precio_unitario_present=primer_item.precio_unitario_paquete if primer_item else None,
                )
                # Se guarda también en el historial de la sesión, para
                # feedback inmediato sin tener que releer toda la BD.
                st.session_state["ventas_sesion"].insert(
                    0,
                    {
                        "Fecha": str(fecha_venta),
                        "Cliente": cliente.strip(),
                        "Tipo": resultado.tipo_huevo,
                        "Unidades": resultado.unidades_cubiertas,
                        "Total": formato_cop(resultado.total),
                    },
                )
                st.success(
                    f"Venta registrada: {resultado.unidades_cubiertas} unidades de "
                    f"{resultado.tipo_huevo} por {formato_cop(resultado.total)}."
                )
                st.rerun()

    st.markdown("---")
    if st.session_state["ventas_sesion"]:
        st.subheader("Ventas registradas en esta sesión")
        st.dataframe(
            pd.DataFrame(st.session_state["ventas_sesion"]),
            width="stretch",
            hide_index=True,
        )

    st.subheader("Historial completo de ventas")
    ventas = db.obtener_ventas()
    if ventas:
        st.dataframe(pd.DataFrame(ventas), width="stretch", hide_index=True)
    else:
        st.info("Aún no hay ventas registradas.")


# ==================================================================
# 5. INVENTARIO
# ==================================================================
elif seccion == "📦 Inventario":
    st.title("Inventario de Huevos")
    inventario = calc.resumen_inventario_en_cubetas()
    df = pd.DataFrame(inventario)
    if df.empty:
        st.info("Sin datos de inventario todavía.")
    else:
        df_mostrar = df.rename(
            columns={
                "tipo_huevo": "Tipo",
                "entradas_producidas": "Entradas (u.)",
                "salidas_vendidas": "Salidas (u.)",
                "stock_disponible": "Stock (u.)",
                "equivalencia_cubetas": "Equivalencia",
                "precio_ref_unidad": "Precio ref./u.",
                "valor_inventario_estimado": "Valor estimado",
            }
        )
        st.dataframe(df_mostrar, width="stretch", hide_index=True)
        st.metric("Valor total estimado del inventario", formato_cop(df["valor_inventario_estimado"].sum()))


# ==================================================================
# 6. GASTOS
# ==================================================================
elif seccion == "💸 Gastos":
    st.title("Registrar Gastos")

    with st.form("form_gasto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha_gasto = st.date_input("Fecha", value=date.today())
            tipo_gasto = st.selectbox(
                "Tipo de gasto",
                ["Alimento", "Medicamentos/Vacunas", "Servicios", "Mano de obra", "Otro"],
            )
        with col2:
            descripcion = st.text_input("Proveedor / Descripción")
            cantidad = st.number_input("Cantidad (opcional, ej. sacos, kg)", min_value=0.0, step=1.0)
        costo_total = st.number_input("Costo total (COP)", min_value=0.0, step=1000.0)

        enviado = st.form_submit_button("Guardar gasto")
        if enviado:
            db.registrar_gasto(fecha_gasto, tipo_gasto, descripcion.strip(), cantidad, costo_total)
            st.success(f"Gasto registrado: {formato_cop(costo_total)} en {tipo_gasto}.")

    st.markdown("---")
    st.subheader("Historial de gastos")
    gastos = db.obtener_gastos()
    if gastos:
        st.dataframe(pd.DataFrame(gastos), width="stretch", hide_index=True)
    else:
        st.info("Aún no hay gastos registrados.")


# ==================================================================
# 7. CONFIGURAR PRECIOS
# ==================================================================
elif seccion == "⚙️ Configurar Precios":
    st.title("Configuración de Tabla de Precios")
    st.write(
        "Ajusta el precio de cada presentación por tipo de huevo. "
        "Estos valores alimentan la calculadora del Punto de Venta."
    )

    precios = db.obtener_precios()
    tipo_sel = st.selectbox("Tipo de huevo", db.TIPOS_HUEVO, key="precios_tipo")

    st.markdown(f"#### Precios actuales — {tipo_sel}")
    cols = st.columns(len(db.PRESENTACIONES))
    nuevos_valores = {}
    for i, presentacion in enumerate(db.PRESENTACIONES):
        valor_actual = precios.get(tipo_sel, {}).get(presentacion, 0)
        with cols[i]:
            nuevos_valores[presentacion] = st.number_input(
                etiqueta_presentacion(presentacion),
                min_value=0.0,
                step=100.0,
                value=float(valor_actual),
                key=f"precio_{tipo_sel}_{presentacion}",
            )

    if st.button("Guardar cambios de precio"):
        for presentacion, valor in nuevos_valores.items():
            db.actualizar_precio(tipo_sel, presentacion, valor)
        st.success(f"Precios actualizados para {tipo_sel}.")

    st.markdown("---")
    st.subheader("Tabla completa de precios")
    filas = []
    precios_actualizados = db.obtener_precios()
    for tipo, tabla in precios_actualizados.items():
        fila = {"Tipo": tipo}
        for p in db.PRESENTACIONES:
            fila[f"{p} u."] = formato_cop(tabla.get(p, 0))
        filas.append(fila)
    st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)

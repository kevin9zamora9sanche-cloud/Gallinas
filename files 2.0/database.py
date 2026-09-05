"""
database.py
------------------------------------------------------------
Capa de persistencia (SQLite) para el Sistema de Control Avícola.

Responsabilidades:
    - Crear y versionar el esquema de la base de datos.
    - Sembrar datos de referencia (clasificación NTC 1240 y tabla
      de precios) replicando la estructura del libro de Excel
      original (hojas: Produccion, Ingresos, Gastos,
      Precios_Referencia, Inventario_Huevos).
    - Exponer funciones de acceso a datos (CRUD) que usa la capa
      de negocio (calculadora.py) y la interfaz (app.py).

No contiene lógica de presentación ni reglas de negocio de
clasificación/precio; eso vive en calculadora.py.
------------------------------------------------------------
"""

import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = "avicola.db"

# Tipos de huevo manejados por el sistema, en el mismo orden que la
# tabla Precios_Referencia del Excel original (de menor a mayor tamaño).
TIPOS_HUEVO = ["Tipo C", "Tipo B", "Tipo A", "Tipo AA", "Tipo AAA", "Jumbo"]

# Presentaciones (paquetes) que maneja el negocio, en unidades de huevo.
# 30 = cubeta completa; 1 = unidad suelta.
PRESENTACIONES = [30, 20, 15, 12, 10, 6, 1]

# Rangos de peso NTC 1240 (Icontec) en gramos: (tipo, peso_min_incl, peso_max_incl_o_None)
# peso_max_incl = None significa "sin límite superior" (Jumbo).
CLASIFICACION_NTC1240 = [
    ("Tipo C", 0.0, 45.9),
    ("Tipo B", 46.0, 52.9),
    ("Tipo A", 53.0, 59.9),
    ("Tipo AA", 60.0, 66.9),
    ("Tipo AAA", 67.0, 77.9),
    ("Jumbo", 78.0, None),
]

# Precios de referencia iniciales (COP) por tipo y presentación,
# tomados como semilla desde la hoja Precios_Referencia del Excel.
# Estructura: {tipo_huevo: {presentacion: precio_total_paquete}}
PRECIOS_SEMILLA = {
    "Tipo C":   {30: 13000, 20: 8700,  15: 6500, 12: 5200, 10: 4400, 6: 2600, 1: 400},
    "Tipo B":   {30: 14000, 20: 9700,  15: 7300, 12: 5800, 10: 4900, 6: 2900, 1: 500},
    "Tipo A":   {30: 15000, 20: 10700, 15: 8000, 12: 6400, 10: 5400, 6: 3200, 1: 600},
    "Tipo AA":  {30: 21000, 20: 13000, 15: 9800, 12: 7800, 10: 6500, 6: 3900, 1: 700},
    "Tipo AAA": {30: 23500, 20: 15700, 15: 11800, 12: 9400, 10: 7900, 6: 4700, 1: 800},
    # Jumbo no existía en la hoja original; se estima con un 12% sobre AAA
    # y debe ajustarse desde el módulo de configuración de precios.
    "Jumbo":    {30: 26300, 20: 17600, 15: 13200, 12: 10500, 10: 8850, 6: 5260, 1: 900},
}


@contextmanager
def get_connection():
    """Provee una conexión SQLite con row_factory tipo dict y claves foráneas activas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Crea las tablas si no existen y siembra datos de referencia."""
    with get_connection() as conn:
        cur = conn.cursor()

        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS clasificacion_ntc1240 (
                tipo_huevo   TEXT PRIMARY KEY,
                peso_min_g   REAL NOT NULL,
                peso_max_g   REAL          -- NULL = sin tope superior (Jumbo)
            );

            CREATE TABLE IF NOT EXISTS precios (
                tipo_huevo   TEXT NOT NULL,
                presentacion INTEGER NOT NULL,   -- unidades por paquete
                precio       REAL NOT NULL,      -- precio total del paquete (COP)
                PRIMARY KEY (tipo_huevo, presentacion)
            );

            CREATE TABLE IF NOT EXISTS produccion (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha             TEXT NOT NULL,
                galpon            TEXT NOT NULL,
                tipo_huevo        TEXT NOT NULL,
                aves_iniciales    INTEGER NOT NULL DEFAULT 0,
                mortalidad        INTEGER NOT NULL DEFAULT 0,
                huevos_recogidos  INTEGER NOT NULL DEFAULT 0,
                huevos_rotos      INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ventas (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha                    TEXT NOT NULL,
                cliente                  TEXT NOT NULL,
                tipo_huevo               TEXT NOT NULL,
                presentacion             INTEGER,   -- NULL si fue cálculo dinámico por unidades sueltas
                cantidad_paquetes        INTEGER,
                precio_unitario_present  REAL,
                total_unidades_vendidas  INTEGER NOT NULL,
                total_ingreso            REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS gastos (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha                  TEXT NOT NULL,
                tipo_gasto             TEXT NOT NULL,
                proveedor_descripcion  TEXT,
                cantidad               REAL,
                costo_total            REAL NOT NULL
            );
            """
        )

        # --- Semilla: clasificación NTC 1240 ---
        cur.execute("SELECT COUNT(*) AS n FROM clasificacion_ntc1240")
        if cur.fetchone()["n"] == 0:
            cur.executemany(
                "INSERT INTO clasificacion_ntc1240 (tipo_huevo, peso_min_g, peso_max_g) VALUES (?, ?, ?)",
                CLASIFICACION_NTC1240,
            )

        # --- Semilla: tabla de precios ---
        cur.execute("SELECT COUNT(*) AS n FROM precios")
        if cur.fetchone()["n"] == 0:
            filas = [
                (tipo, presentacion, precio)
                for tipo, tabla in PRECIOS_SEMILLA.items()
                for presentacion, precio in tabla.items()
            ]
            cur.executemany(
                "INSERT INTO precios (tipo_huevo, presentacion, precio) VALUES (?, ?, ?)",
                filas,
            )


# ------------------------------------------------------------------
# PRODUCCIÓN
# ------------------------------------------------------------------
def registrar_produccion(fecha, galpon, tipo_huevo, aves_iniciales, mortalidad,
                          huevos_recogidos, huevos_rotos):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO produccion
               (fecha, galpon, tipo_huevo, aves_iniciales, mortalidad,
                huevos_recogidos, huevos_rotos)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(fecha), galpon, tipo_huevo, aves_iniciales, mortalidad,
             huevos_recogidos, huevos_rotos),
        )


def obtener_produccion():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM produccion ORDER BY fecha DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# VENTAS
# ------------------------------------------------------------------
def registrar_venta(fecha, cliente, tipo_huevo, total_unidades, total_ingreso,
                     presentacion=None, cantidad_paquetes=None, precio_unitario_present=None):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO ventas
               (fecha, cliente, tipo_huevo, presentacion, cantidad_paquetes,
                precio_unitario_present, total_unidades_vendidas, total_ingreso)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(fecha), cliente, tipo_huevo, presentacion, cantidad_paquetes,
             precio_unitario_present, total_unidades, total_ingreso),
        )


def obtener_ventas():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ventas ORDER BY fecha DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# GASTOS
# ------------------------------------------------------------------
def registrar_gasto(fecha, tipo_gasto, descripcion, cantidad, costo_total):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO gastos (fecha, tipo_gasto, proveedor_descripcion, cantidad, costo_total)
               VALUES (?, ?, ?, ?, ?)""",
            (str(fecha), tipo_gasto, descripcion, cantidad, costo_total),
        )


def obtener_gastos():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM gastos ORDER BY fecha DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# PRECIOS / CONFIGURACIÓN
# ------------------------------------------------------------------
def obtener_precios():
    """Devuelve un dict {tipo_huevo: {presentacion: precio}}."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM precios").fetchall()
    tabla = {t: {} for t in TIPOS_HUEVO}
    for r in rows:
        tabla[r["tipo_huevo"]][r["presentacion"]] = r["precio"]
    return tabla


def actualizar_precio(tipo_huevo, presentacion, nuevo_precio):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO precios (tipo_huevo, presentacion, precio)
               VALUES (?, ?, ?)
               ON CONFLICT(tipo_huevo, presentacion) DO UPDATE SET precio = excluded.precio""",
            (tipo_huevo, presentacion, nuevo_precio),
        )


def obtener_clasificacion_ntc1240():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM clasificacion_ntc1240 ORDER BY peso_min_g ASC"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------------
# INVENTARIO (derivado de producción y ventas, igual que la hoja
# Inventario_Huevos del Excel: Entradas - Salidas = Stock)
# ------------------------------------------------------------------
def obtener_inventario():
    with get_connection() as conn:
        entradas = conn.execute(
            """SELECT tipo_huevo, COALESCE(SUM(huevos_recogidos - huevos_rotos), 0) AS entradas
               FROM produccion GROUP BY tipo_huevo"""
        ).fetchall()
        salidas = conn.execute(
            """SELECT tipo_huevo, COALESCE(SUM(total_unidades_vendidas), 0) AS salidas
               FROM ventas GROUP BY tipo_huevo"""
        ).fetchall()
        precios_ref = conn.execute(
            "SELECT tipo_huevo, precio FROM precios WHERE presentacion = 1"
        ).fetchall()

    entradas_map = {r["tipo_huevo"]: r["entradas"] for r in entradas}
    salidas_map = {r["tipo_huevo"]: r["salidas"] for r in salidas}
    precio_unidad_map = {r["tipo_huevo"]: r["precio"] for r in precios_ref}

    inventario = []
    for tipo in TIPOS_HUEVO:
        ent = entradas_map.get(tipo, 0)
        sal = salidas_map.get(tipo, 0)
        stock = ent - sal
        precio_unidad = precio_unidad_map.get(tipo, 0)
        inventario.append(
            {
                "tipo_huevo": tipo,
                "entradas_producidas": ent,
                "salidas_vendidas": sal,
                "stock_disponible": stock,
                "precio_ref_unidad": precio_unidad,
                "valor_inventario_estimado": stock * precio_unidad,
            }
        )
    return inventario


def obtener_resumen_dashboard():
    with get_connection() as conn:
        total_ingresos = conn.execute(
            "SELECT COALESCE(SUM(total_ingreso), 0) AS t FROM ventas"
        ).fetchone()["t"]
        total_gastos = conn.execute(
            "SELECT COALESCE(SUM(costo_total), 0) AS t FROM gastos"
        ).fetchone()["t"]
        total_huevos_producidos = conn.execute(
            "SELECT COALESCE(SUM(huevos_recogidos), 0) AS t FROM produccion"
        ).fetchone()["t"]

    return {
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "ganancia_neta": total_ingresos - total_gastos,
        "total_huevos_producidos": total_huevos_producidos,
    }


if __name__ == "__main__":
    # Permite inicializar la BD ejecutando: python database.py
    init_db()
    print(f"Base de datos inicializada en '{DB_PATH}'.")

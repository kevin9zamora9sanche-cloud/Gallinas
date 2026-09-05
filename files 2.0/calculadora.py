"""
calculadora.py
------------------------------------------------------------
Lógica de negocio del Sistema de Control Avícola:

    1. Clasificación de huevos según la norma técnica colombiana
       NTC 1240 (Icontec), a partir del peso en gramos.
    2. Conversión inteligente de unidades sueltas a cubetas
       (1 cubeta = 30 unidades) con residuo.
    3. Calculadora de precios (POS):
         a) Precio por presentación específica (paquete configurado).
         b) Precio dinámico óptimo: dado un total de unidades a
            vender, calcula la combinación de presentaciones que
            minimiza el número de paquetes / maximiza el valor,
            usando la tabla de precios configurada en la BD.

Depende únicamente de funciones de solo-lectura de database.py
(no abre conexiones propias), para mantener una separación clara
entre persistencia y reglas de negocio.
------------------------------------------------------------
"""

from dataclasses import dataclass, field
from typing import List, Optional

import database as db


class PesoFueraDeRangoError(Exception):
    """Se lanza cuando un peso no encaja en ningún rango NTC 1240 (p. ej. negativo)."""


# ------------------------------------------------------------------
# 1. CLASIFICACIÓN NTC 1240
# ------------------------------------------------------------------
def clasificar_huevo_por_peso(peso_gramos: float) -> str:
    """
    Devuelve el tipo de huevo (NTC 1240) correspondiente a un peso en gramos.

    Rangos (Icontec NTC 1240):
        Tipo C   : < 46.0 g
        Tipo B   : 46.0 - 52.9 g
        Tipo A   : 53.0 - 59.9 g
        Tipo AA  : 60.0 - 66.9 g
        Tipo AAA : 67.0 - 77.9 g
        Jumbo    : >= 78.0 g
    """
    if peso_gramos is None or peso_gramos <= 0:
        raise PesoFueraDeRangoError("El peso del huevo debe ser un número positivo.")

    rangos = db.obtener_clasificacion_ntc1240()
    for r in rangos:
        piso = r["peso_min_g"]
        techo = r["peso_max_g"]
        if techo is None:  # categoría abierta hacia arriba (Jumbo)
            if peso_gramos >= piso:
                return r["tipo_huevo"]
        else:
            if piso <= peso_gramos <= techo:
                return r["tipo_huevo"]

    # No debería ocurrir si la tabla de clasificación cubre 0..inf,
    # pero se deja como salvaguarda.
    raise PesoFueraDeRangoError(f"No se encontró clasificación NTC 1240 para {peso_gramos} g.")


# ------------------------------------------------------------------
# 2. CONVERSIÓN INTELIGENTE UNIDADES <-> CUBETAS
# ------------------------------------------------------------------
UNIDADES_POR_CUBETA = 30


def convertir_unidades_a_cubetas(unidades: int) -> dict:
    """
    Convierte un número de unidades sueltas a cubetas completas + residuo.

    Ejemplo: 94 unidades -> 3 cubetas + 4 unidades sueltas.
    """
    if unidades < 0:
        raise ValueError("El número de unidades no puede ser negativo.")

    cubetas = unidades // UNIDADES_POR_CUBETA
    sueltas = unidades % UNIDADES_POR_CUBETA
    return {
        "unidades_totales": unidades,
        "cubetas_completas": cubetas,
        "unidades_sueltas": sueltas,
        "descripcion": f"{cubetas} cubeta(s) + {sueltas} unidad(es) suelta(s)"
        if sueltas
        else f"{cubetas} cubeta(s) exacta(s)",
    }


def convertir_cubetas_a_unidades(cubetas: float) -> int:
    """Convierte cubetas (puede ser fraccionario, ej. 1.5) a unidades enteras."""
    if cubetas < 0:
        raise ValueError("El número de cubetas no puede ser negativo.")
    return round(cubetas * UNIDADES_POR_CUBETA)


# ------------------------------------------------------------------
# 3. CALCULADORA DE PRECIOS (POS)
# ------------------------------------------------------------------
@dataclass
class ItemVenta:
    """Una línea de la combinación óptima de paquetes para una venta."""
    presentacion: int
    cantidad_paquetes: int
    precio_unitario_paquete: float
    subtotal: float = field(init=False)

    def __post_init__(self):
        self.subtotal = self.cantidad_paquetes * self.precio_unitario_paquete


@dataclass
class ResultadoVenta:
    tipo_huevo: str
    unidades_solicitadas: int
    items: List[ItemVenta]
    total: float
    unidades_cubiertas: int

    @property
    def precio_promedio_unidad(self) -> float:
        if self.unidades_cubiertas == 0:
            return 0.0
        return self.total / self.unidades_cubiertas


def calcular_precio_por_presentacion(tipo_huevo: str, presentacion: int,
                                      cantidad_paquetes: int) -> ResultadoVenta:
    """
    Calcula el total para una venta de una presentación específica
    (ej. 5 cubetas de Tipo AA), tal como se registra en la hoja
    'Ingresos' del Excel original.
    """
    precios = db.obtener_precios()
    if tipo_huevo not in precios:
        raise ValueError(f"Tipo de huevo desconocido: {tipo_huevo}")
    if presentacion not in precios[tipo_huevo]:
        raise ValueError(f"No hay precio configurado para {tipo_huevo} / presentación {presentacion}")

    precio_unit = precios[tipo_huevo][presentacion]
    item = ItemVenta(presentacion, cantidad_paquetes, precio_unit)
    total_unidades = presentacion * cantidad_paquetes

    return ResultadoVenta(
        tipo_huevo=tipo_huevo,
        unidades_solicitadas=total_unidades,
        items=[item],
        total=item.subtotal,
        unidades_cubiertas=total_unidades,
    )


def calcular_precio_dinamico(tipo_huevo: str, unidades: int) -> ResultadoVenta:
    """
    Calculadora "inteligente": dado un número total de unidades a vender,
    descompone la cantidad en la combinación de presentaciones disponibles
    (30, 20, 15, 12, 10, 6, 1...) que la cubre usando primero los paquetes
    más grandes (mejor precio por unidad), de forma análoga a como un
    vendedor arma cubetas completas y despacha el resto en paquetes menores.

    No asume que las presentaciones dividen exactamente las unidades: si
    sobra un residuo menor a la presentación más pequeña, se completa con
    unidades sueltas (presentación = 1).
    """
    if unidades <= 0:
        raise ValueError("Las unidades a vender deben ser mayores a cero.")

    precios = db.obtener_precios()
    if tipo_huevo not in precios:
        raise ValueError(f"Tipo de huevo desconocido: {tipo_huevo}")

    tabla_precios = precios[tipo_huevo]
    # Orden descendente de presentaciones disponibles y con precio configurado
    presentaciones_disp = sorted(
        [p for p, precio in tabla_precios.items() if precio and precio > 0],
        reverse=True,
    )
    if 1 not in presentaciones_disp:
        raise ValueError(
            f"Falta configurar el precio por unidad suelta (presentación=1) para {tipo_huevo}."
        )

    restante = unidades
    items: List[ItemVenta] = []
    for presentacion in presentaciones_disp:
        if presentacion == 1:
            continue  # las unidades sueltas se resuelven al final con el residuo
        if restante >= presentacion:
            cantidad_paquetes = restante // presentacion
            restante -= cantidad_paquetes * presentacion
            items.append(ItemVenta(presentacion, cantidad_paquetes, tabla_precios[presentacion]))

    if restante > 0:
        items.append(ItemVenta(1, restante, tabla_precios[1]))

    total = sum(item.subtotal for item in items)
    unidades_cubiertas = sum(item.presentacion * item.cantidad_paquetes for item in items)

    return ResultadoVenta(
        tipo_huevo=tipo_huevo,
        unidades_solicitadas=unidades,
        items=items,
        total=total,
        unidades_cubiertas=unidades_cubiertas,
    )


def resumen_inventario_en_cubetas() -> List[dict]:
    """
    Devuelve el inventario actual por tipo, agregando la equivalencia
    en cubetas + sueltas para lectura rápida en el dashboard.
    """
    inventario = db.obtener_inventario()
    resultado = []
    for fila in inventario:
        conv = convertir_unidades_a_cubetas(max(fila["stock_disponible"], 0))
        resultado.append({**fila, "equivalencia_cubetas": conv["descripcion"]})
    return resultado

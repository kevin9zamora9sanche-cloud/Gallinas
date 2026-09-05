# Sistema de Control Avícola

## 🖱️ Uso rápido en Windows (doble clic)

Requisito único: tener **Python instalado** (https://www.python.org/downloads/,
marcando la casilla "Add Python to PATH" durante la instalación).

**Paso 1 — Crear el acceso directo (solo la primera vez):**
Haz doble clic en `crear_acceso_directo.vbs`. Esto crea un ícono llamado
**"Control Avícola"** en tu Escritorio.

**Paso 2 — Usar la app:**
Desde ahora, haz doble clic en el ícono **"Control Avícola"** del Escritorio
cada vez que quieras abrir el sistema. Se abrirá una ventana negra (no la
cierres mientras trabajas) y el navegador se abrirá automáticamente con la
aplicación.

La primera vez que la abras tardará un poco más porque instala las
dependencias necesarias (Streamlit, pandas) en un entorno virtual local
dentro de la misma carpeta (`venv\`). Las siguientes veces abrirá casi
de inmediato.

**Para cerrar la app:** simplemente cierra la ventana negra (consola).

> Si mueves la carpeta del proyecto a otro lugar, vuelve a ejecutar
> `crear_acceso_directo.vbs` para que el acceso directo apunte a la
> nueva ubicación.

---

## Instalación manual (alternativa, cualquier sistema operativo)
```bash
pip install -r requirements.txt
```

## Ejecución manual
```bash
streamlit run app.py
```

Al arrancar, `app.py` crea automáticamente el archivo `avicola.db` (SQLite)
en la misma carpeta y lo siembra con:
- La tabla de clasificación NTC 1240 (Icontec) por peso en gramos.
- La tabla de precios de referencia por tipo de huevo y presentación,
  tomada de la hoja `Precios_Referencia` del Excel original.

## Estructura
- `database.py`    -> Esquema SQLite + funciones CRUD (producción, ventas, gastos, precios, inventario).
- `calculadora.py` -> Reglas de negocio: clasificador NTC 1240, conversión a cubetas (30 u.) y calculadora de precios (por presentación o dinámica).
- `app.py`         -> Interfaz Streamlit (Dashboard, Producción, Clasificador, POS, Inventario, Gastos, Configurar Precios).
- `iniciar_app.bat` -> Launcher de Windows: crea el entorno virtual, instala dependencias y arranca la app.
- `crear_acceso_directo.vbs` -> Crea el ícono "Control Avícola" en el Escritorio (ejecutar una sola vez).

## Notas sobre la NTC 1240
Rangos usados (Icontec NTC 1240):
| Tipo | Peso (g) |
|------|----------|
| C    | < 46.0 |
| B    | 46.0 - 52.9 |
| A    | 53.0 - 59.9 |
| AA   | 60.0 - 66.9 |
| AAA  | 67.0 - 77.9 |
| Jumbo| ≥ 78.0 |

Estos valores son ampliamente citados como los de la norma vigente, pero
se recomienda verificarlos contra el texto oficial de Icontec si se usan
para efectos de certificación o auditoría. Los precios de "Jumbo" en la
semilla son un estimado (+12% sobre AAA) porque esa categoría no existía
en el Excel original — ajústalos en "Configurar Precios" antes de usarlos.

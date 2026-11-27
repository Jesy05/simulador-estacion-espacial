# Simulador · Estación espacial (Challenge #4)

Simulador de un robot que recoge un módulo de comunicaciones y lo entrega en la zona de
ensamblaje. Recibe código Python, lo valida con `ast` y ejecuta las instrucciones paso a paso.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `simulador.py` | **Archivo principal.** Mapa, estado del robot, validación con `ast`, reglas de las acciones y modo consola. |
| `interfaz.py` | Interfaz gráfica (tkinter): bloques arrastrables, editor de Python, mapa animado, estado y registro. |
| `pruebas.py` | Ejecuta los seis casos de la guía y compara el resultado observado con el esperado. |
| `evidencia_casos.md` | Salida de los seis casos (se genera con `python pruebas.py --md`). |

| `index.html`, `web/` | Versión web (GitHub Pages). Ejecuta **el mismo `simulador.py`** con Python 3 dentro del navegador (Pyodide). |

Solo necesita **Python 3** (tkinter viene incluido). No hay que instalar nada.

**Versión web:** https://jesy05.github.io/simulador-estacion-espacial/ — la misma interfaz de bloques y Python,
sin instalar nada. La validación y las reglas no están reescritas en JavaScript: la página descarga
`simulador.py` y lo ejecuta con Python 3 (Pyodide).

## Cómo usarlo

### Interfaz gráfica
```
python simulador.py
```
1. Arma el programa con los **bloques** de la izquierda (clic para añadir al final, o arrástralos
   a una posición). Para reordenar, arrastra un bloque dentro del programa; para borrarlo, arrástralo
   fuera, haz clic derecho o pulsa ✕.
2. O cambia a la pestaña **Python** y escribe las llamadas (`mover("este")`, `recoger()`, `entregar()`),
   una por línea. Las dos vistas están sincronizadas.
3. **Funciones propias:** con **＋ Crear función** armas tu propia función (por ejemplo `dar_vuelta`)
   con su pila de bloques, y la usas con el bloque morado **llamar dar_vuelta()**. En Python es lo mismo
   con `def` (ver abajo).
4. Pulsa **▶ Ejecutar**. El robot se mueve en el mapa y se resalta la instrucción en curso.
5. **↺ Reiniciar** vuelve al estado inicial para hacer una nueva prueba. En **Caso de prueba** puedes
   cargar los seis casos de la guía y cuatro ejemplos con funciones propias.

### Consola
```
python simulador.py --consola
```
Escribe el código línea por línea y termina con `FIN`. Al final pregunta si quieres hacer otra prueba
desde el estado inicial.

### Casos de prueba
```
python pruebas.py        # muestra los seis casos de la guía y los cuatro ejemplos con funciones
python pruebas.py --md   # además guarda evidencia_casos.md
```

## Reglas implementadas

- Mapa 5 × 5 en coordenadas `(fila, columna)` desde 1. Robot en (1, 1), módulo en (1, 3),
  entrega en (3, 4), obstáculos en (2, 3) y (4, 2).
- 8 unidades de energía; cada movimiento válido gasta 1; recoger y entregar gastan 0.
- `mover("norte")` resta una fila, `"sur"` suma una fila, `"oeste"` resta una columna, `"este"` suma una columna.
- `recoger()` solo en (1, 3) y con el módulo disponible. `entregar()` solo en (3, 4) y con el módulo a bordo.
- Tres resultados: **Misión completada**, **Misión incompleta** y **Misión detenida por error**
  (además de **Código rechazado** cuando la validación previa falla y no se ejecuta nada).

## Funciones propias

Además de las tres acciones del robot, el programa puede definir sus propias funciones con `def`
y llamarlas. Sirven para agrupar movimientos y reutilizarlos:

```python
def ir_al_modulo():
    """Avanza por la fila 1 hasta la celda del módulo."""
    mover("este")
    mover("este")

def bajar_a_la_entrega():
    mover("este")
    mover("sur")
    mover("sur")

def mision():
    ir_al_modulo()
    recoger()
    bajar_a_la_entrega()
    entregar()

mision()
```

Reglas de las funciones (todas se revisan con `ast` antes de ejecutar):

- Se definen con `def nombre():` **sin parámetros**, decoradores ni `async`.
- Su cuerpo solo puede tener llamadas a `mover`, `recoger`, `entregar` u otras funciones propias
  (se permiten un docstring y `pass`).
- No pueden llamarse `mover`, `recoger` ni `entregar`, ni definirse dos veces.
- En el programa principal, como en Python, una función debe estar definida **antes** de usarla.
- No se permiten llamadas circulares (una función que se llama a sí misma, directa o indirectamente),
  porque el robot nunca terminaría.
- Si una acción falla dentro de una función, el mensaje dice la línea de la acción **y** desde qué
  línea se llamó la función, por ejemplo:
  *«Misión detenida por error en la línea 3 (dentro de dar_vuelta(), llamada en la línea 10): falta de energía…»*.

## Qué parte valida las instrucciones

`validar_codigo()` en `simulador.py` (que usa `analizar_programa()` y `expandir()`):

1. `ast.parse(codigo)`; un error de sintaxis se informa con su línea.
2. Recorre `arbol.body`. Acepta `ast.FunctionDef` (funciones propias, revisadas por `_revisar_funcion`)
   y `ast.Expr` cuyo valor sea `ast.Call` con `func` de tipo `ast.Name` (revisado por `_revisar_llamada`).
   Cualquier otra sentencia (`for`, `if`, asignaciones, `import`…) se rechaza.
3. Rechaza argumentos con nombre (`keywords`), cantidades de argumentos incorrectas y, en `mover`,
   cualquier argumento que no sea un `ast.Constant` de texto con una dirección válida.
4. Comprueba que cada nombre llamado sea una acción del robot o una función propia definida, y que no
   haya llamadas circulares.
5. `expandir()` convierte el programa en la lista de acciones básicas en el orden en que se ejecutan
   (recordando desde qué función viene cada una).
6. Todo esto ocurre **antes** de ejecutar la primera acción. Si algo falla, informa la línea y el robot
   conserva el estado inicial.

Durante la ejecución, cada acción comprueba sus reglas **antes** de cambiar el estado
(`Simulador.mover/recoger/entregar`). Si una regla falla se lanza `ErrorDeAccion`, la misión se detiene
y la posición, la energía y el módulo quedan como estaban.

## Uso de IA

- **Herramienta:** Claude (Anthropic), usado como asistente de programación.
- **Prompt inicial:**
  > Ayúdame a crear en Python 3 un simulador de un robot que transporta un módulo espacial. Usa las
  > reglas del escenario y los requisitos de implementación que voy a pegar a continuación. La aplicación
  > debe solicitar código Python de varias líneas, validar las llamadas del robot antes de ejecutarlas y
  > mostrar el estado final. Explícame cómo ejecutar el programa y qué parte valida las instrucciones. Te
  > compartiré los resultados de mis pruebas para corregir los fallos que encuentre.
  >
  > (Además pedimos una interfaz con bloques, parecida a Open Roberta, que genere el mismo código Python.)
- **Decisiones y cambios después de revisar y probar:**
  - *Validar antes de ejecutar.* La validación con `ast` está separada de la ejecución
    (`validar_codigo` y `Simulador.ejecutar_instruccion`). Así, en el caso 6 (`volar()` en la línea 2)
    el robot no hace ni el primer `mover("este")`, como pide la guía.
  - *No modificar el estado en una acción rechazada.* Cada acción revisa energía, límites y obstáculos
    **antes** de cambiar la posición o la energía. Lo comprobamos con el caso 2: el robot se queda en
    (1, 3) con 6 de energía y el módulo a bordo.
  - *Bloques que generan Python.* Los bloques no ejecutan nada por su cuenta: generan el texto Python
    y ese texto pasa por la misma validación con `ast`. Así hay una sola forma de interpretar el programa.
  - *Funciones propias.* El profesor pidió que, además de llamar a `mover`, `recoger` y `entregar`,
    pudiéramos construir nuestras propias funciones (por ejemplo `dar_vuelta()`). Ampliamos la
    validación para aceptar `def` sin parámetros, comprobar que no haya llamadas circulares y
    «expandir» cada función en sus acciones antes de ejecutar. Los seis casos de la guía siguen dando
    el mismo resultado, y agregamos cuatro ejemplos más (casos 7 a 10) para probar las funciones.
  - *Pantallas con zoom.* En la primera versión la ventana se veía cortada en una pantalla con zoom
    del 150 %. Agregamos un factor de escala según los DPI del monitor.

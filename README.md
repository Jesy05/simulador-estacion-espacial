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

Solo necesita **Python 3** (tkinter viene incluido). No hay que instalar nada.

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
3. Pulsa **▶ Ejecutar**. El robot se mueve en el mapa y se resalta la instrucción en curso.
4. **↺ Reiniciar** vuelve al estado inicial para hacer una nueva prueba. En **Caso de prueba** puedes
   cargar cualquiera de los seis casos de la guía.

### Consola
```
python simulador.py --consola
```
Escribe el código línea por línea y termina con `FIN`. Al final pregunta si quieres hacer otra prueba
desde el estado inicial.

### Casos de prueba
```
python pruebas.py        # muestra los seis casos
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

## Qué parte valida las instrucciones

`validar_codigo()` en `simulador.py`:

1. `ast.parse(codigo)`; un error de sintaxis se informa con su línea.
2. Recorre `arbol.body` y acepta solo `ast.Expr` cuyo valor sea `ast.Call` con `func` de tipo `ast.Name`
   y nombre `mover`, `recoger` o `entregar`.
3. Rechaza argumentos con nombre (`keywords`), cantidades de argumentos incorrectas y, en `mover`,
   cualquier argumento que no sea un `ast.Constant` de texto con una dirección válida.
4. Revisa **todo** el programa antes de ejecutar la primera acción. Si algo falla, informa la línea y
   el robot conserva el estado inicial.

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
  - *Pantallas con zoom.* En la primera versión la ventana se veía cortada en una pantalla con zoom
    del 150 %. Agregamos un factor de escala según los DPI del monitor.

"""
Ejecuta los seis casos de prueba de la guía y compara con el resultado esperado.

    python pruebas.py          -> muestra cada caso en consola
    python pruebas.py --md     -> además guarda evidencia_casos.md
"""

import sys
from simulador import (Simulador, informe, COMPLETADA, DETENIDA, RECHAZADO,
                       DISPONIBLE, A_BORDO, ENTREGADO)

ESTE, OESTE, SUR = 'mover("este")', 'mover("oeste")', 'mover("sur")'

# (nombre, código, resultado esperado según la guía, comprobación: tipo, línea, posición, energía, módulo)
CASOS = [
    ("1. Entrega exitosa",
     [ESTE, ESTE, "recoger()", ESTE, SUR, SUR, "entregar()"],
     "Misión completada en (3, 4), con 3 unidades de energía y el módulo entregado.",
     (COMPLETADA, None, (3, 4), 3, ENTREGADO)),
    ("2. Choque con obstáculo",
     [ESTE, ESTE, "recoger()", SUR],
     "Misión detenida en la línea 4. Hay un obstáculo en (2, 3). El robot permanece en (1, 3) "
     "con 6 unidades de energía y el módulo a bordo.",
     (DETENIDA, 4, (1, 3), 6, A_BORDO)),
    ("3. Salida del mapa",
     ['mover("norte")'],
     "Misión detenida en la línea 1 por salida del mapa. El robot permanece en (1, 1) con 8 "
     "unidades de energía y el módulo sigue disponible.",
     (DETENIDA, 1, (1, 1), 8, DISPONIBLE)),
    ("4. Entrega sin carga",
     [ESTE, ESTE, ESTE, SUR, SUR, "entregar()"],
     "Misión detenida en la línea 6. El robot está en (3, 4), con 3 unidades de energía y sin "
     "el módulo a bordo.",
     (DETENIDA, 6, (3, 4), 3, DISPONIBLE)),
    ("5. Energía agotada",
     [ESTE, OESTE, ESTE, OESTE, ESTE, OESTE, ESTE, OESTE, ESTE],
     "Misión detenida en la línea 9 por falta de energía. El robot permanece en (1, 1), con 0 "
     "unidades de energía y el módulo disponible.",
     (DETENIDA, 9, (1, 1), 0, DISPONIBLE)),
    ("6. Instrucción desconocida",
     [ESTE, "volar()"],
     "Código rechazado en la línea 2 por una instrucción desconocida. No se ejecuta ninguna "
     "acción. El robot conserva el estado inicial.",
     (RECHAZADO, 2, (1, 1), 8, DISPONIBLE)),
]


def correr():
    sim = Simulador()
    salida_md = ["# Evidencia de los seis casos de prueba", ""]
    aprobados = 0
    for nombre, lineas, esperado, (tipo, linea, pos, energia, modulo) in CASOS:
        codigo = "\n".join(lineas)
        r = sim.ejecutar(codigo)
        ok = (r.tipo == tipo and r.linea == linea and r.estado.posicion == pos
              and r.estado.energia == energia and r.estado.modulo == modulo)
        aprobados += ok
        bloque = [f"## {nombre}", "", "**Código ingresado**", "", "```python", codigo, "```", "",
                  f"**Resultado esperado:** {esperado}", "",
                  f"**Resultado observado:** {r.mensaje()}", "",
                  f"**¿Coincide?** {'Sí' if ok else 'NO'}", "",
                  "**Salida del simulador**", "", "```", informe(r).strip(), "```", ""]
        salida_md += bloque
        print("=" * 70)
        print(nombre)
        print("-" * 70)
        print(codigo)
        print(informe(r))
        print(f"\nEsperado: {esperado}")
        print(f"Coincide: {'SÍ' if ok else 'NO'}")
    print("=" * 70)
    print(f"{aprobados} de {len(CASOS)} casos coinciden con lo esperado.")
    if "--md" in sys.argv:
        with open("evidencia_casos.md", "w", encoding="utf-8") as f:
            f.write("\n".join(salida_md))
        print("Evidencia guardada en evidencia_casos.md")
    return aprobados == len(CASOS)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if correr() else 1)

# Evidencia de los seis casos de prueba

## 1. Entrega exitosa

**Código ingresado**

```python
mover("este")
mover("este")
recoger()
mover("este")
mover("sur")
mover("sur")
entregar()
```

**Resultado esperado:** Misión completada en (3, 4), con 3 unidades de energía y el módulo entregado.

**Resultado observado:** Misión completada en (3, 4), con 3 unidades de energía y el módulo entregado.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
Línea 1: mover este → (1, 2), energía 7
Línea 2: mover este → (1, 3), energía 6
Línea 3: recoger → módulo a bordo
Línea 4: mover este → (1, 4), energía 5
Línea 5: mover sur → (2, 4), energía 4
Línea 6: mover sur → (3, 4), energía 3
Línea 7: entregar → módulo entregado

=== Mapa final ===
      1   2   3   4   5
  1   ·   ·   ·   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   R   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (3, 4) · energía 3 · módulo entregado

=== Resultado ===
Misión completada en (3, 4), con 3 unidades de energía y el módulo entregado.
```

## 2. Choque con obstáculo

**Código ingresado**

```python
mover("este")
mover("este")
recoger()
mover("sur")
```

**Resultado esperado:** Misión detenida en la línea 4. Hay un obstáculo en (2, 3). El robot permanece en (1, 3) con 6 unidades de energía y el módulo a bordo.

**Resultado observado:** Misión detenida por error en la línea 4: hay un obstáculo en (2, 3). El robot permanece en (1, 3) con 6 unidades de energía y el módulo a bordo.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
Línea 1: mover este → (1, 2), energía 7
Línea 2: mover este → (1, 3), energía 6
Línea 3: recoger → módulo a bordo
Línea 4: mover("sur") RECHAZADA (hay un obstáculo en (2, 3))

=== Mapa final ===
      1   2   3   4   5
  1   ·   ·   R   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   E   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (1, 3) · energía 6 · módulo a bordo

=== Resultado ===
Misión detenida por error en la línea 4: hay un obstáculo en (2, 3). El robot permanece en (1, 3) con 6 unidades de energía y el módulo a bordo.
```

## 3. Salida del mapa

**Código ingresado**

```python
mover("norte")
```

**Resultado esperado:** Misión detenida en la línea 1 por salida del mapa. El robot permanece en (1, 1) con 8 unidades de energía y el módulo sigue disponible.

**Resultado observado:** Misión detenida por error en la línea 1: salida del mapa: (0, 1) está fuera. El robot permanece en (1, 1) con 8 unidades de energía y el módulo disponible.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
Línea 1: mover("norte") RECHAZADA (salida del mapa: (0, 1) está fuera)

=== Mapa final ===
      1   2   3   4   5
  1   R   ·   M   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   E   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (1, 1) · energía 8 · módulo disponible

=== Resultado ===
Misión detenida por error en la línea 1: salida del mapa: (0, 1) está fuera. El robot permanece en (1, 1) con 8 unidades de energía y el módulo disponible.
```

## 4. Entrega sin carga

**Código ingresado**

```python
mover("este")
mover("este")
mover("este")
mover("sur")
mover("sur")
entregar()
```

**Resultado esperado:** Misión detenida en la línea 6. El robot está en (3, 4), con 3 unidades de energía y sin el módulo a bordo.

**Resultado observado:** Misión detenida por error en la línea 6: no se puede entregar sin el módulo a bordo. El robot permanece en (3, 4) con 3 unidades de energía y el módulo disponible.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
Línea 1: mover este → (1, 2), energía 7
Línea 2: mover este → (1, 3), energía 6
Línea 3: mover este → (1, 4), energía 5
Línea 4: mover sur → (2, 4), energía 4
Línea 5: mover sur → (3, 4), energía 3
Línea 6: entregar() RECHAZADA (no se puede entregar sin el módulo a bordo)

=== Mapa final ===
      1   2   3   4   5
  1   ·   ·   M   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   R   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (3, 4) · energía 3 · módulo disponible

=== Resultado ===
Misión detenida por error en la línea 6: no se puede entregar sin el módulo a bordo. El robot permanece en (3, 4) con 3 unidades de energía y el módulo disponible.
```

## 5. Energía agotada

**Código ingresado**

```python
mover("este")
mover("oeste")
mover("este")
mover("oeste")
mover("este")
mover("oeste")
mover("este")
mover("oeste")
mover("este")
```

**Resultado esperado:** Misión detenida en la línea 9 por falta de energía. El robot permanece en (1, 1), con 0 unidades de energía y el módulo disponible.

**Resultado observado:** Misión detenida por error en la línea 9: falta de energía. El robot permanece en (1, 1) con 0 unidades de energía y el módulo disponible.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
Línea 1: mover este → (1, 2), energía 7
Línea 2: mover oeste → (1, 1), energía 6
Línea 3: mover este → (1, 2), energía 5
Línea 4: mover oeste → (1, 1), energía 4
Línea 5: mover este → (1, 2), energía 3
Línea 6: mover oeste → (1, 1), energía 2
Línea 7: mover este → (1, 2), energía 1
Línea 8: mover oeste → (1, 1), energía 0
Línea 9: mover("este") RECHAZADA (falta de energía)

=== Mapa final ===
      1   2   3   4   5
  1   R   ·   M   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   E   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (1, 1) · energía 0 · módulo disponible

=== Resultado ===
Misión detenida por error en la línea 9: falta de energía. El robot permanece en (1, 1) con 0 unidades de energía y el módulo disponible.
```

## 6. Instrucción desconocida

**Código ingresado**

```python
mover("este")
volar()
```

**Resultado esperado:** Código rechazado en la línea 2 por una instrucción desconocida. No se ejecuta ninguna acción. El robot conserva el estado inicial.

**Resultado observado:** Código rechazado en la línea 2: instrucción desconocida «volar». No se ejecuta ninguna acción. El robot conserva el estado inicial.

**¿Coincide?** Sí

**Salida del simulador**

```
=== Registro de acciones ===
(ninguna acción ejecutada)

=== Mapa final ===
      1   2   3   4   5
  1   R   ·   M   ·   ·
  2   ·   ·   #   ·   ·
  3   ·   ·   ·   E   ·
  4   ·   #   ·   ·   ·
  5   ·   ·   ·   ·   ·
  R = robot · M = módulo · E = entrega · # = obstáculo

=== Estado del robot ===
Posición (1, 1) · energía 8 · módulo disponible

=== Resultado ===
Código rechazado en la línea 2: instrucción desconocida «volar». No se ejecuta ninguna acción. El robot conserva el estado inicial.
```

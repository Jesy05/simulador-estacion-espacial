"""
Simulador de la estación espacial — Challenge #4 (Transporte de componentes espaciales).

Archivo principal. Contiene:
  * el modelo del robot y del mapa (Estado),
  * la validación del código Python con ast (validar_codigo),
  * la ejecución de las acciones con sus reglas (Simulador),
  * el modo consola (python simulador.py --consola).

Sin argumentos abre la interfaz gráfica (interfaz.py).
"""

import ast
import sys
from dataclasses import dataclass, field

# ----------------------------------------------------------------------------
# Escenario (coordenadas (fila, columna), empezando en 1)
# ----------------------------------------------------------------------------
FILAS = 5
COLUMNAS = 5
INICIO = (1, 1)
POS_MODULO = (1, 3)
POS_ENTREGA = (3, 4)
OBSTACULOS = {(2, 3), (4, 2)}
ENERGIA_INICIAL = 8

DIRECCIONES = {
    "norte": (-1, 0),   # resta una fila
    "sur": (1, 0),      # suma una fila
    "oeste": (0, -1),   # resta una columna
    "este": (0, 1),     # suma una columna
}

# nombre de la función -> cantidad de argumentos que acepta
FUNCIONES = {"mover": 1, "recoger": 0, "entregar": 0}

# estados posibles del módulo
DISPONIBLE = "disponible"
A_BORDO = "a bordo"
ENTREGADO = "entregado"

# resultados posibles de una misión
COMPLETADA = "Misión completada"
INCOMPLETA = "Misión incompleta"
DETENIDA = "Misión detenida por error"
RECHAZADO = "Código rechazado"


# ----------------------------------------------------------------------------
# Modelo
# ----------------------------------------------------------------------------
@dataclass
class Estado:
    posicion: tuple = INICIO
    energia: int = ENERGIA_INICIAL
    modulo: str = DISPONIBLE
    registro: list = field(default_factory=list)

    def resumen(self):
        fila, col = self.posicion
        return (f"Posición ({fila}, {col}) · energía {self.energia} · "
                f"módulo {self.modulo}")


@dataclass
class Instruccion:
    linea: int
    nombre: str
    argumentos: tuple

    def como_texto(self):
        if self.nombre == "mover":
            return f'mover("{self.argumentos[0]}")'
        return f"{self.nombre}()"


class ErrorDeCodigo(Exception):
    """El código no cumple las reglas: no se ejecuta ninguna acción."""

    def __init__(self, linea, motivo):
        super().__init__(f"Línea {linea}: {motivo}")
        self.linea = linea
        self.motivo = motivo


class ErrorDeAccion(Exception):
    """Una acción incumple una regla de la misión: se detiene la ejecución."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


# ----------------------------------------------------------------------------
# Validación previa con ast
# ----------------------------------------------------------------------------
def validar_codigo(codigo):
    """Revisa TODO el código antes de ejecutar la primera acción.

    Devuelve la lista de Instruccion. Si algo no es válido lanza ErrorDeCodigo
    con el número de línea y el motivo.
    """
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as e:
        raise ErrorDeCodigo(e.lineno or 1, f"error de sintaxis ({e.msg})")

    instrucciones = []
    for sentencia in arbol.body:
        linea = sentencia.lineno

        # Solo se aceptan expresiones sueltas que sean una llamada: mover("este")
        if not isinstance(sentencia, ast.Expr) or not isinstance(sentencia.value, ast.Call):
            raise ErrorDeCodigo(linea, "solo se permiten llamadas a mover(), recoger() o entregar()")

        llamada = sentencia.value
        if not isinstance(llamada.func, ast.Name):
            raise ErrorDeCodigo(linea, "instrucción desconocida")

        nombre = llamada.func.id
        if nombre not in FUNCIONES:
            raise ErrorDeCodigo(linea, f"instrucción desconocida «{nombre}»")

        if llamada.keywords:
            raise ErrorDeCodigo(linea, f"{nombre}() no acepta argumentos con nombre")

        esperados = FUNCIONES[nombre]
        if len(llamada.args) != esperados:
            if esperados == 0:
                raise ErrorDeCodigo(linea, f"{nombre}() no lleva argumentos")
            raise ErrorDeCodigo(linea, f"{nombre}() necesita exactamente {esperados} argumento")

        argumentos = []
        for arg in llamada.args:
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                raise ErrorDeCodigo(linea, f"{nombre}() necesita un texto entre comillas")
            if arg.value not in DIRECCIONES:
                raise ErrorDeCodigo(linea, f"dirección «{arg.value}» no válida "
                                           "(usa norte, sur, este u oeste)")
            argumentos.append(arg.value)

        instrucciones.append(Instruccion(linea, nombre, tuple(argumentos)))
    return instrucciones


# ----------------------------------------------------------------------------
# Simulador: aplica las acciones y comprueba las reglas
# ----------------------------------------------------------------------------
class Simulador:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.estado = Estado()
        self.terminado = False

    # --- acciones -----------------------------------------------------------
    def mover(self, direccion):
        df, dc = DIRECCIONES[direccion]
        fila, col = self.estado.posicion
        destino = (fila + df, col + dc)
        # Se revisa todo ANTES de cambiar el estado: si algo falla, nada cambia.
        if self.estado.energia <= 0:
            raise ErrorDeAccion("falta de energía")
        if not (1 <= destino[0] <= FILAS and 1 <= destino[1] <= COLUMNAS):
            raise ErrorDeAccion(f"salida del mapa: ({destino[0]}, {destino[1]}) está fuera")
        if destino in OBSTACULOS:
            raise ErrorDeAccion(f"hay un obstáculo en ({destino[0]}, {destino[1]})")
        self.estado.posicion = destino
        self.estado.energia -= 1
        return f"mover {direccion} → ({destino[0]}, {destino[1]}), energía {self.estado.energia}"

    def recoger(self):
        if self.estado.posicion != POS_MODULO:
            raise ErrorDeAccion(f"para recoger el robot debe estar en {POS_MODULO}")
        if self.estado.modulo != DISPONIBLE:
            raise ErrorDeAccion("el módulo no está disponible para recoger")
        self.estado.modulo = A_BORDO
        return "recoger → módulo a bordo"

    def entregar(self):
        if self.estado.posicion != POS_ENTREGA:
            raise ErrorDeAccion(f"para entregar el robot debe estar en {POS_ENTREGA}")
        if self.estado.modulo != A_BORDO:
            raise ErrorDeAccion("no se puede entregar sin el módulo a bordo")
        self.estado.modulo = ENTREGADO
        return "entregar → módulo entregado"

    # --- despacho -----------------------------------------------------------
    def ejecutar_instruccion(self, instr):
        """Ejecuta UNA instrucción ya validada. Lanza ErrorDeAccion si incumple una regla."""
        accion = getattr(self, instr.nombre)
        detalle = accion(*instr.argumentos)
        self.estado.registro.append(f"Línea {instr.linea}: {detalle}")
        if self.estado.modulo == ENTREGADO:
            self.terminado = True
        return detalle

    def ejecutar(self, codigo):
        """Valida y ejecuta un programa completo desde el estado inicial."""
        self.reiniciar()
        try:
            instrucciones = validar_codigo(codigo)
        except ErrorDeCodigo as e:
            return Resultado(RECHAZADO, e.linea, e.motivo, self.estado)
        for instr in instrucciones:
            try:
                self.ejecutar_instruccion(instr)
            except ErrorDeAccion as e:
                self.estado.registro.append(f"Línea {instr.linea}: {instr.como_texto()} RECHAZADA ({e.motivo})")
                return Resultado(DETENIDA, instr.linea, e.motivo, self.estado)
            if self.terminado:
                return Resultado(COMPLETADA, None, None, self.estado)
        return Resultado(INCOMPLETA, None, "el programa terminó antes de entregar el módulo", self.estado)


@dataclass
class Resultado:
    tipo: str
    linea: int
    motivo: str
    estado: Estado

    def mensaje(self):
        e = self.estado
        fila, col = e.posicion
        estado_txt = (f"El robot permanece en ({fila}, {col}) con {e.energia} "
                      f"unidad{'es' if e.energia != 1 else ''} de energía y el módulo {e.modulo}.")
        if self.tipo == COMPLETADA:
            return (f"{COMPLETADA} en ({fila}, {col}), con {e.energia} unidades de energía "
                    f"y el módulo entregado.")
        if self.tipo == RECHAZADO:
            return (f"{RECHAZADO} en la línea {self.linea}: {self.motivo}. "
                    f"No se ejecuta ninguna acción. El robot conserva el estado inicial.")
        if self.tipo == DETENIDA:
            return f"{DETENIDA} en la línea {self.linea}: {self.motivo}. {estado_txt}"
        return f"{INCOMPLETA}: {self.motivo}. {estado_txt}"


# ----------------------------------------------------------------------------
# Dibujo del mapa en texto (consola y pruebas)
# ----------------------------------------------------------------------------
def mapa_texto(estado):
    simbolos = []
    simbolos.append("      " + "   ".join(str(c) for c in range(1, COLUMNAS + 1)))
    for f in range(1, FILAS + 1):
        celdas = []
        for c in range(1, COLUMNAS + 1):
            p = (f, c)
            if p == estado.posicion:
                s = "R"
            elif p in OBSTACULOS:
                s = "#"
            elif p == POS_MODULO and estado.modulo == DISPONIBLE:
                s = "M"
            elif p == POS_ENTREGA:
                s = "E"
            else:
                s = "·"
            celdas.append(s)
        simbolos.append(f"  {f}   " + "   ".join(celdas))
    simbolos.append("  R = robot · M = módulo · E = entrega · # = obstáculo")
    return "\n".join(simbolos)


def informe(resultado):
    e = resultado.estado
    partes = ["", "=== Registro de acciones ==="]
    partes += e.registro or ["(ninguna acción ejecutada)"]
    partes += ["", "=== Mapa final ===", mapa_texto(e), "",
               "=== Estado del robot ===", e.resumen(), "",
               "=== Resultado ===", resultado.mensaje()]
    return "\n".join(partes)


# ----------------------------------------------------------------------------
# Modo consola
# ----------------------------------------------------------------------------
def leer_codigo_consola():
    print("Escribe el código de la misión. Termina con FIN en una línea sola.")
    lineas = []
    while True:
        try:
            linea = input("> ")
        except EOFError:
            break
        if linea.strip() == "FIN":
            break
        lineas.append(linea)
    return "\n".join(lineas)


def modo_consola():
    sim = Simulador()
    print("Simulador de la estación espacial · Challenge #4")
    print(mapa_texto(sim.estado))
    while True:
        print()
        codigo = leer_codigo_consola()
        print(informe(sim.ejecutar(codigo)))
        otra = input("\n¿Nueva prueba desde el estado inicial? (s/n) ").strip().lower()
        if otra != "s":
            break


if __name__ == "__main__":
    if "--consola" in sys.argv:
        modo_consola()
    else:
        from interfaz import iniciar_interfaz
        iniciar_interfaz()

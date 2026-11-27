"""
Simulador de la estación espacial — Challenge #4 (Transporte de componentes espaciales).

Archivo principal. Contiene:
  * el modelo del robot y del mapa (Estado),
  * la validación del código Python con ast (validar_codigo), que acepta las
    acciones del robot y funciones propias definidas con def,
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
    """Una acción básica (mover, recoger o entregar) lista para ejecutarse."""
    linea: int
    nombre: str
    argumentos: tuple
    pila: tuple = ()        # ((función, línea donde se llamó), ...) si viene de una función propia

    def como_texto(self):
        if self.nombre == "mover":
            return f'mover("{self.argumentos[0]}")'
        return f"{self.nombre}()"

    def donde(self):
        """Texto que explica desde qué función propia viene la acción."""
        if not self.pila:
            return ""
        funcion, linea_llamada = self.pila[-1]
        return f" (dentro de {funcion}(), llamada en la línea {linea_llamada})"


@dataclass
class Llamada:
    linea: int
    nombre: str
    argumentos: tuple


@dataclass
class FuncionPropia:
    nombre: str
    linea: int
    llamadas: list


@dataclass
class Programa:
    funciones: dict     # nombre -> FuncionPropia (en el orden en que se definieron)
    principal: list     # llamadas del programa principal


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
MAX_ACCIONES = 500      # límite para programas que, por funciones anidadas, crecen demasiado


def _es_docstring(sentencia):
    return (isinstance(sentencia, ast.Expr) and isinstance(sentencia.value, ast.Constant)
            and isinstance(sentencia.value.value, str))


def _revisar_llamada(sentencia, dentro_de=None):
    """Comprueba que la sentencia sea una llamada directa y devuelve una Llamada.

    Solo revisa la forma; si el nombre es una función propia se resuelve después.
    """
    linea = sentencia.lineno
    if not isinstance(sentencia, ast.Expr) or not isinstance(sentencia.value, ast.Call):
        if dentro_de:
            raise ErrorDeCodigo(linea, f"dentro de {dentro_de}() solo puede haber llamadas a "
                                       "mover(), recoger(), entregar() o a otras funciones tuyas")
        raise ErrorDeCodigo(linea, "solo se permiten llamadas a mover(), recoger() o entregar() "
                                   "y definiciones de funciones con def")
    llamada = sentencia.value
    if not isinstance(llamada.func, ast.Name):
        raise ErrorDeCodigo(linea, "instrucción desconocida")
    nombre = llamada.func.id
    if llamada.keywords:
        raise ErrorDeCodigo(linea, f"{nombre}() no acepta argumentos con nombre")

    if nombre not in FUNCIONES:
        # puede ser una función propia: no lleva argumentos
        if llamada.args:
            raise ErrorDeCodigo(linea, f"{nombre}() no lleva argumentos (tus funciones no tienen parámetros)")
        return Llamada(linea, nombre, ())

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
    return Llamada(linea, nombre, tuple(argumentos))


def _revisar_funcion(nodo):
    """Comprueba una definición def nombre(): ... y devuelve una FuncionPropia."""
    linea = nodo.lineno
    if isinstance(nodo, ast.AsyncFunctionDef):
        raise ErrorDeCodigo(linea, "las funciones no pueden ser async")
    if nodo.name in FUNCIONES:
        raise ErrorDeCodigo(linea, f"no puedes redefinir {nodo.name}(): es una acción del robot")
    a = nodo.args
    if a.posonlyargs or a.args or a.kwonlyargs or a.vararg or a.kwarg:
        raise ErrorDeCodigo(linea, f"{nodo.name}() no puede tener parámetros")
    if nodo.decorator_list:
        raise ErrorDeCodigo(linea, f"{nodo.name}() no puede tener decoradores")
    if nodo.returns:
        raise ErrorDeCodigo(linea, f"{nodo.name}() no puede tener anotación de retorno")
    cuerpo = nodo.body[1:] if _es_docstring(nodo.body[0]) else nodo.body
    llamadas = []
    for sentencia in cuerpo:
        if isinstance(sentencia, ast.Pass):
            continue
        if isinstance(sentencia, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ErrorDeCodigo(sentencia.lineno, "no se permiten funciones dentro de otra función")
        llamadas.append(_revisar_llamada(sentencia, dentro_de=nodo.name))
    return FuncionPropia(nodo.name, linea, llamadas)


def analizar_programa(codigo):
    """Lee el código con ast y devuelve un Programa (funciones propias + programa principal)."""
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as e:
        raise ErrorDeCodigo(e.lineno or 1, f"error de sintaxis ({e.msg})")

    funciones, principal = {}, []
    for sentencia in arbol.body:
        if isinstance(sentencia, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if sentencia.name in funciones:
                raise ErrorDeCodigo(sentencia.lineno, f"la función {sentencia.name}() ya estaba definida "
                                                      f"en la línea {funciones[sentencia.name].linea}")
            funciones[sentencia.name] = _revisar_funcion(sentencia)
        else:
            principal.append(_revisar_llamada(sentencia))

    # Los nombres usados deben existir. En el programa principal, como en Python,
    # la función tiene que estar definida ANTES de la línea donde se llama.
    def comprobar(llamada, dentro_de=None):
        if llamada.nombre in FUNCIONES:
            return
        f = funciones.get(llamada.nombre)
        if f is None:
            raise ErrorDeCodigo(llamada.linea, f"instrucción desconocida «{llamada.nombre}»")
        if dentro_de is None and f.linea > llamada.linea:
            raise ErrorDeCodigo(llamada.linea, f"{llamada.nombre}() se usa antes de definirla "
                                               f"(está en la línea {f.linea})")

    for f in funciones.values():
        for llamada in f.llamadas:
            comprobar(llamada, dentro_de=f.nombre)
    for llamada in principal:
        comprobar(llamada)

    # Una función no puede llamarse a sí misma, ni directa ni indirectamente.
    estado = {}

    def visitar(nombre, cadena):
        estado[nombre] = "visitando"
        for llamada in funciones[nombre].llamadas:
            if llamada.nombre not in funciones:
                continue
            if estado.get(llamada.nombre) == "visitando":
                ciclo = " → ".join(cadena + [nombre, llamada.nombre])
                raise ErrorDeCodigo(llamada.linea, f"llamada circular entre funciones ({ciclo}): "
                                                   "el robot nunca terminaría")
            if llamada.nombre not in estado:
                visitar(llamada.nombre, cadena + [nombre])
        estado[nombre] = "lista"

    for nombre in funciones:
        if nombre not in estado:
            visitar(nombre, [])
    return Programa(funciones, principal)


def expandir(programa):
    """Convierte el Programa en la lista plana de acciones básicas, en orden de ejecución."""
    instrucciones = []

    def agregar(llamada, pila):
        if llamada.nombre in FUNCIONES:
            instrucciones.append(Instruccion(llamada.linea, llamada.nombre, llamada.argumentos, pila))
            if len(instrucciones) > MAX_ACCIONES:
                raise ErrorDeCodigo(llamada.linea, f"el programa genera más de {MAX_ACCIONES} acciones")
            return
        for interna in programa.funciones[llamada.nombre].llamadas:
            agregar(interna, pila + ((llamada.nombre, llamada.linea),))

    for llamada in programa.principal:
        agregar(llamada, ())
    return instrucciones


def validar_codigo(codigo):
    """Revisa TODO el código antes de ejecutar la primera acción.

    Acepta llamadas a mover/recoger/entregar y funciones propias definidas con def
    (sin parámetros) que agrupan esas llamadas. Devuelve la lista de Instruccion ya
    expandida. Si algo no es válido lanza ErrorDeCodigo con la línea y el motivo.
    """
    return expandir(analizar_programa(codigo))


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
        self.estado.registro.append(f"Línea {instr.linea}: {detalle}{instr.donde()}")
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
                self.estado.registro.append(f"Línea {instr.linea}: {instr.como_texto()}{instr.donde()} "
                                            f"RECHAZADA ({e.motivo})")
                return Resultado(DETENIDA, instr.linea, e.motivo, self.estado, instr.donde())
            if self.terminado:
                return Resultado(COMPLETADA, None, None, self.estado)
        return Resultado(INCOMPLETA, None, "el programa terminó antes de entregar el módulo", self.estado)


@dataclass
class Resultado:
    tipo: str
    linea: int
    motivo: str
    estado: Estado
    donde: str = ""     # " (dentro de f(), llamada en la línea N)" si el error vino de una función propia

    def mensaje(self):
        e = self.estado
        fila, col = e.posicion
        estado_txt = (f"El robot permanece en ({fila}, {col}) con {e.energia} "
                      f"unidad{'es' if e.energia != 1 else ''} de energía y el módulo {e.modulo}.")
        if self.tipo == COMPLETADA:
            return (f"{COMPLETADA} en ({fila}, {col}), con {e.energia} "
                    f"unidad{'es' if e.energia != 1 else ''} de energía "
                    f"y el módulo entregado.")
        if self.tipo == RECHAZADO:
            return (f"{RECHAZADO} en la línea {self.linea}: {self.motivo}. "
                    f"No se ejecuta ninguna acción. El robot conserva el estado inicial.")
        if self.tipo == DETENIDA:
            return f"{DETENIDA} en la línea {self.linea}{self.donde}: {self.motivo}. {estado_txt}"
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

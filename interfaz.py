"""
Interfaz gráfica del simulador (tkinter, incluido con Python 3).

Dos formas de programar la misión, siempre sincronizadas:
  * Bloques: arrastra o haz clic en los bloques de la izquierda para armar el programa.
    Con «Crear función» armas tus propias funciones (cada una con su pila de bloques).
  * Python: escribe mover(...), recoger(), entregar() y tus funciones con def.

El código final SIEMPRE pasa por simulador.validar_codigo (ast) antes de ejecutarse.
"""

import keyword
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

from simulador import (Simulador, validar_codigo, analizar_programa, ErrorDeCodigo, ErrorDeAccion,
                       Resultado, DIRECCIONES, FUNCIONES,
                       FILAS, COLUMNAS, OBSTACULOS, POS_MODULO, POS_ENTREGA, ENERGIA_INICIAL,
                       COMPLETADA, INCOMPLETA, DETENIDA, RECHAZADO, A_BORDO, ENTREGADO)
from pruebas import TODOS as CASOS

# ----------------------------------------------------------------------------
# Estilo
# ----------------------------------------------------------------------------
FONDO = "#0b1020"
PANEL = "#141c36"
PANEL_2 = "#1b2546"
BORDE = "#2a3766"
TEXTO = "#e6ebff"
TEXTO_SUAVE = "#93a0c8"
ACENTO = "#5b8cff"
VERDE = "#22c55e"
NARANJA = "#f59e0b"
ROJO = "#ef4444"
FUENTE = "Segoe UI"
MONO = "Consolas"

# nombre del bloque -> (texto, color, (función, argumento))
BLOQUES = {
    "norte": ("mover  ↑ norte", "#3b82f6", ("mover", "norte")),
    "sur": ("mover  ↓ sur", "#3b82f6", ("mover", "sur")),
    "este": ("mover  → este", "#3b82f6", ("mover", "este")),
    "oeste": ("mover  ← oeste", "#3b82f6", ("mover", "oeste")),
    "recoger": ("recoger  módulo", "#f59e0b", ("recoger", None)),
    "entregar": ("entregar  módulo", "#22c55e", ("entregar", None)),
}

ALTO_BLOQUE = 34
SEP_BLOQUE = 4
CELDA = 62


MORADO = "#9333ea"
ALTO_CABEZA = 36


def clave_de(nombre, arg):
    if nombre == "mover":
        return arg
    if nombre in FUNCIONES:
        return nombre
    return "fn:" + nombre           # llamada a una función propia


def info_bloque(clave):
    """(texto, color, línea de Python) de un bloque."""
    if clave.startswith("fn:"):
        nombre = clave[3:]
        return f"llamar  {nombre}()", MORADO, f"{nombre}()"
    texto, color, (nombre, arg) = BLOQUES[clave]
    return texto, color, (f'mover("{arg}")' if nombre == "mover" else f"{nombre}()")


def linea_python(clave):
    return info_bloque(clave)[2]


def rect_redondo(canvas, x1, y1, x2, y2, r=10, **kw):
    puntos = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(puntos, smooth=True, **kw)


def aclarar(color, factor=0.25):
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * factor) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# ----------------------------------------------------------------------------
# Aplicación
# ----------------------------------------------------------------------------
class App:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title("Simulador · Estación espacial (Challenge #4)")
        raiz.configure(bg=FONDO)
        # factor de escala de la pantalla (100 % = 1.0, 150 % = 1.5): todo se dibuja en
        # coordenadas base y luego se escala, así se ve igual en cualquier monitor
        self.S = max(1.0, raiz.winfo_fpixels("1i") / 96.0)
        S = self.S
        ancho_pant, alto_pant = raiz.winfo_screenwidth(), raiz.winfo_screenheight()
        raiz.geometry(f"{min(int(1280 * S), ancho_pant - 40)}x{min(int(720 * S), alto_pant - 90)}+10+10")
        raiz.minsize(min(int(1100 * S), ancho_pant - 40), min(int(620 * S), alto_pant - 90))
        try:
            raiz.state("zoomed")    # maximizada en Windows
        except tk.TclError:
            pass

        self.sim = Simulador()
        self.principal = []         # claves de bloque del programa principal: "este", "recoger", "fn:x"...
        self.funciones = []         # [{"nombre": str, "cuerpo": [claves]}]
        self.disposicion = []       # posición de cada pila en el lienzo (se calcula al dibujar)
        self.vista = "bloques"      # "bloques" o "python"
        self.ejecutando = False
        self.tarea = None
        self.arrastre = None
        self.rastro = [self.sim.estado.posicion]
        self.linea_a_bloque = {}

        self._estilos()
        self._construir()
        self._redibujar_programa()
        self._dibujar_mapa()
        self._actualizar_estado()
        self._mostrar_resultado(None)

    # --- construcción -------------------------------------------------------
    def _estilos(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXTO,
                     arrowcolor=TEXTO, bordercolor=BORDE)
        st.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXTO)])
        st.configure("Horizontal.TScale", background=PANEL, troughcolor=PANEL_2)

    def _tarjeta(self, padre, titulo):
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(marco, text=titulo, bg=PANEL, fg=TEXTO_SUAVE, font=(FUENTE, 10, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        return marco

    def _boton(self, padre, texto, comando, color=ACENTO, ancho=None):
        b = tk.Button(padre, text=texto, command=comando, bg=color, fg="white",
                      activebackground=aclarar(color), activeforeground="white", relief="flat",
                      font=(FUENTE, 10, "bold"), padx=12, pady=6, cursor="hand2", bd=0)
        if ancho:
            b.configure(width=ancho)
        return b

    def _construir(self):
        cab = tk.Frame(self.raiz, bg=FONDO)
        cab.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(cab, text="Estación espacial · Transporte del módulo", bg=FONDO, fg=TEXTO,
                 font=(FUENTE, 17, "bold")).pack(anchor="w")
        tk.Label(cab, text="Programa con bloques o con Python · el código se valida con ast antes de ejecutarse",
                 bg=FONDO, fg=TEXTO_SUAVE, font=(FUENTE, 10)).pack(anchor="w")

        cuerpo = tk.Frame(self.raiz, bg=FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        # ---- columna 1: paleta de bloques
        paleta = self._tarjeta(cuerpo, "BLOQUES")
        paleta.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        tk.Label(paleta, text="Clic para añadir al final\no arrastra al programa", bg=PANEL,
                 fg=TEXTO_SUAVE, font=(FUENTE, 9), justify="left").pack(anchor="w", padx=12)
        self.cv_paleta = tk.Canvas(paleta, width=int(200 * self.S), height=int(310 * self.S), bg=PANEL,
                                   highlightthickness=0)
        self.cv_paleta.pack(padx=10, pady=8)
        for i, (clave, (texto, color, _)) in enumerate(BLOQUES.items()):
            y = 8 + i * (ALTO_BLOQUE + 16)
            etiqueta = f"pal_{clave}"
            rect_redondo(self.cv_paleta, 6, y, 192, y + ALTO_BLOQUE + 4, r=10, fill=color,
                         outline=aclarar(color, .35), width=1, tags=(etiqueta,))
            self.cv_paleta.create_text(20, y + ALTO_BLOQUE / 2 + 2, text=texto, anchor="w", fill="white",
                                       font=(FUENTE, 11, "bold"), tags=(etiqueta,))
            self.cv_paleta.tag_bind(etiqueta, "<ButtonPress-1>", lambda e, k=clave: self._paleta_presionar(e, k))
            self.cv_paleta.tag_bind(etiqueta, "<B1-Motion>", self._arrastre_mover)
            self.cv_paleta.tag_bind(etiqueta, "<ButtonRelease-1>", self._arrastre_soltar)
            self.cv_paleta.tag_bind(etiqueta, "<Enter>", lambda e: self.cv_paleta.configure(cursor="hand2"))
        self.cv_paleta.scale("all", 0, 0, self.S, self.S)

        tk.Label(paleta, text="MIS FUNCIONES", bg=PANEL, fg=TEXTO_SUAVE, font=(FUENTE, 10, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(4, 0))
        self.btn_nueva_funcion = self._boton(paleta, "＋  Crear función", self.crear_funcion, "#7c3aed")
        self.btn_nueva_funcion.pack(fill="x", padx=12, pady=(4, 6))
        self.cv_funciones = tk.Canvas(paleta, width=int(200 * self.S), height=1, bg=PANEL, highlightthickness=0)
        self.cv_funciones.pack(padx=10)

        ayuda = ("Reglas\n• Inicio en (1, 1) con 8 de energía\n• Cada movimiento gasta 1\n"
                 "• recoger() en (1, 3)\n• entregar() en (3, 4)\n• Obstáculos en (2, 3) y (4, 2)")
        tk.Label(paleta, text=ayuda, bg=PANEL, fg=TEXTO_SUAVE, font=(FUENTE, 9), justify="left").pack(
            anchor="w", padx=12, pady=(0, 12))

        # ---- columna 2: programa (bloques / python) + controles
        centro = self.centro = tk.Frame(cuerpo, bg=FONDO)
        centro.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        centro.rowconfigure(1, weight=1)
        centro.columnconfigure(0, weight=1)

        pest = tk.Frame(centro, bg=FONDO)
        pest.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.btn_vista_bloques = self._boton(pest, "🧩  Bloques", lambda: self._cambiar_vista("bloques"))
        self.btn_vista_python = self._boton(pest, "🐍  Python", lambda: self._cambiar_vista("python"))
        self.btn_vista_bloques.pack(side="left")
        self.btn_vista_python.pack(side="left", padx=6)
        self.lbl_aviso = tk.Label(pest, text="", bg=FONDO, fg=NARANJA, font=(FUENTE, 9))
        self.lbl_aviso.pack(side="left", padx=8)

        self.contenedor = tk.Frame(centro, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        self.contenedor.grid(row=1, column=0, sticky="nsew")
        self.contenedor.rowconfigure(0, weight=1)
        self.contenedor.columnconfigure(0, weight=1)

        # vista de bloques
        self.marco_bloques = tk.Frame(self.contenedor, bg=PANEL)
        self.cv_prog = tk.Canvas(self.marco_bloques, bg=PANEL, highlightthickness=0)
        barra = tk.Scrollbar(self.marco_bloques, orient="vertical", command=self.cv_prog.yview)
        self.cv_prog.configure(yscrollcommand=barra.set)
        self.cv_prog.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.cv_prog.bind("<Configure>", lambda e: self._redibujar_programa())
        self.cv_prog.bind("<MouseWheel>", lambda e: self.cv_prog.yview_scroll(-e.delta // 120, "units"))

        # vista de python
        self.marco_python = tk.Frame(self.contenedor, bg=PANEL)
        self.numeros = tk.Text(self.marco_python, width=4, bg=PANEL_2, fg=TEXTO_SUAVE, bd=0,
                               font=(MONO, 12), state="disabled", padx=6, pady=10, takefocus=0)
        self.editor = tk.Text(self.marco_python, bg=PANEL, fg=TEXTO, insertbackground=TEXTO, bd=0,
                              font=(MONO, 12), undo=True, padx=10, pady=10, wrap="none")
        self.numeros.pack(side="left", fill="y")
        self.editor.pack(side="left", fill="both", expand=True)
        self.editor.tag_configure("actual", background="#24407a")
        self.editor.tag_configure("error", background="#5a1f2a")
        self.editor.tag_configure("funcion", foreground="#7fb2ff")
        self.editor.tag_configure("cadena", foreground="#ffcf70")
        self.editor.tag_configure("clave", foreground="#c084fc")
        self.editor.tag_configure("comentario", foreground="#6b7aa6")
        self.editor.bind("<<Modified>>", self._editor_modificado)

        # controles
        ctrl = tk.Frame(centro, bg=FONDO)
        ctrl.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.btn_ejecutar = self._boton(ctrl, "▶  Ejecutar", self.ejecutar, VERDE)
        self.btn_detener = self._boton(ctrl, "■  Detener", self.detener, ROJO)
        self.btn_reiniciar = self._boton(ctrl, "↺  Reiniciar", self.reiniciar, "#475569")
        self.btn_limpiar = self._boton(ctrl, "✕  Borrar", self.limpiar, "#475569")
        for b in (self.btn_ejecutar, self.btn_detener, self.btn_reiniciar, self.btn_limpiar):
            b.pack(side="left", padx=(0, 6))

        ctrl2 = tk.Frame(centro, bg=FONDO)
        ctrl2.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        tk.Label(ctrl2, text="Caso de prueba:", bg=FONDO, fg=TEXTO_SUAVE, font=(FUENTE, 10)).pack(side="left")
        self.combo_caso = ttk.Combobox(ctrl2, values=[c[0] for c in CASOS], state="readonly", width=38)
        self.combo_caso.pack(side="left", padx=6)
        self.combo_caso.bind("<<ComboboxSelected>>", lambda e: self.cargar_caso())
        tk.Label(ctrl2, text="Velocidad", bg=FONDO, fg=TEXTO_SUAVE, font=(FUENTE, 10)).pack(side="left", padx=(16, 4))
        self.velocidad = tk.DoubleVar(value=2)
        ttk.Scale(ctrl2, from_=1, to=4, variable=self.velocidad, length=110).pack(side="left")

        # ---- columna 3: mapa, estado, resultado, registro
        der = tk.Frame(cuerpo, bg=FONDO)
        der.grid(row=0, column=2, sticky="ns")

        mapa = self._tarjeta(der, "MAPA DE LA ESTACIÓN  (fila, columna)")
        mapa.pack(fill="x")
        lado = 30 + CELDA * COLUMNAS + 10
        self.cv_mapa = tk.Canvas(mapa, width=int(lado * self.S), height=int((30 + CELDA * FILAS + 10) * self.S),
                                 bg=PANEL, highlightthickness=0)
        self.cv_mapa.pack(padx=10, pady=(0, 10))

        estado = tk.Frame(der, bg=FONDO)
        estado.pack(fill="x", pady=(10, 0))
        self.lbl_pos = self._indicador(estado, "Posición")
        self.lbl_energia = self._indicador(estado, "Energía")
        self.lbl_modulo = self._indicador(estado, "Módulo")

        self.lbl_resultado = tk.Label(der, text="", bg=PANEL_2, fg=TEXTO, font=(FUENTE, 10, "bold"),
                                      wraplength=int(470 * self.S), justify="left", anchor="w", padx=12, pady=10)
        self.lbl_resultado.pack(fill="x", pady=(10, 0))

        reg = self._tarjeta(self.centro, "REGISTRO DE ACCIONES")
        reg.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.registro = tk.Text(reg, height=7, bg=PANEL, fg=TEXTO, bd=0, font=(MONO, 10),
                                state="disabled", padx=10, wrap="word")
        self.registro.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.registro.tag_configure("error", foreground="#ff8b8b")
        self.registro.tag_configure("ok", foreground="#86efac")

        self._cambiar_vista("bloques")

    def _indicador(self, padre, titulo):
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        marco.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(marco, text=titulo, bg=PANEL, fg=TEXTO_SUAVE, font=(FUENTE, 9)).pack(pady=(6, 0))
        lbl = tk.Label(marco, text="", bg=PANEL, fg=TEXTO, font=(FUENTE, 12, "bold"))
        lbl.pack(pady=(0, 6))
        return lbl

    # --- vistas y sincronización bloques <-> python -------------------------
    def _cambiar_vista(self, vista):
        if vista == "bloques" and self.vista == "python":
            # pasar de Python a bloques: el código debe ser válido
            try:
                self._programa_desde_codigo(self._texto_editor())
            except ErrorDeCodigo as e:
                self._aviso(f"No se puede pasar a bloques — línea {e.linea}: {e.motivo}")
                self._marcar_linea_editor(e.linea, "error")
                return False
        if vista == "python" and self.vista == "bloques":
            self._poner_texto_editor(self._codigo_de_bloques()[0])
        self.vista = vista
        self._aviso("")
        self.marco_bloques.grid_forget()
        self.marco_python.grid_forget()
        if vista == "bloques":
            self.marco_bloques.grid(row=0, column=0, sticky="nsew")
            self._redibujar_programa()
        else:
            self.marco_python.grid(row=0, column=0, sticky="nsew")
            self.editor.focus_set()
        activo, inactivo = ((self.btn_vista_bloques, self.btn_vista_python) if vista == "bloques"
                            else (self.btn_vista_python, self.btn_vista_bloques))
        activo.configure(bg=ACENTO)
        inactivo.configure(bg=PANEL_2)
        return True

    def _lista(self, pila):
        if pila == "principal":
            return self.principal
        for f in self.funciones:
            if "fn:" + f["nombre"] == pila:
                return f["cuerpo"]
        return None

    def _codigo_de_bloques(self):
        """Genera el código Python y el mapa línea -> (pila, índice de bloque)."""
        lineas, mapa = [], {}
        for f in self.funciones:
            lineas.append(f"def {f['nombre']}():")
            if not f["cuerpo"]:
                lineas.append("    pass")
            for i, clave in enumerate(f["cuerpo"]):
                lineas.append("    " + linea_python(clave))
                mapa[len(lineas)] = ("fn:" + f["nombre"], i)
            lineas.append("")
        for i, clave in enumerate(self.principal):
            lineas.append(linea_python(clave))
            mapa[len(lineas)] = ("principal", i)
        return "\n".join(lineas).rstrip("\n"), mapa

    def _programa_desde_codigo(self, codigo):
        """Usa analizar_programa (ast) para pasar de Python a bloques."""
        prog = analizar_programa(codigo)
        mapa = {}

        def claves(llamadas, pila):
            res = []
            for i, ll in enumerate(llamadas):
                mapa[ll.linea] = (pila, i)
                res.append(clave_de(ll.nombre, ll.argumentos[0] if ll.argumentos else None))
            return res

        self.funciones = [{"nombre": f.nombre, "cuerpo": claves(f.llamadas, "fn:" + f.nombre)}
                          for f in prog.funciones.values()]
        self.principal = claves(prog.principal, "principal")
        self.linea_a_bloque = mapa

    def _codigo_actual(self):
        return self._codigo_de_bloques()[0] if self.vista == "bloques" else self._texto_editor()

    def _texto_editor(self):
        return self.editor.get("1.0", "end-1c")

    def _poner_texto_editor(self, texto):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", texto)
        self._colorear()

    def _editor_modificado(self, _evento=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self._colorear()

    def _colorear(self):
        self.editor.tag_remove("funcion", "1.0", "end")
        self.editor.tag_remove("cadena", "1.0", "end")
        self.editor.tag_remove("clave", "1.0", "end")
        self.editor.tag_remove("comentario", "1.0", "end")
        for patron, tag in ((r"\m(mover|recoger|entregar)\M", "funcion"), (r'"[^"]*"', "cadena"),
                            (r"\m(def|pass)\M", "clave"), (r"#[^\n]*", "comentario")):
            inicio = "1.0"
            while True:
                cuenta = tk.IntVar()
                pos = self.editor.search(patron, inicio, "end", regexp=True, count=cuenta)
                if not pos or cuenta.get() == 0:
                    break
                fin = f"{pos}+{cuenta.get()}c"
                self.editor.tag_add(tag, pos, fin)
                inicio = fin
        total = int(self.editor.index("end-1c").split(".")[0])
        self.numeros.configure(state="normal")
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        self.numeros.configure(state="disabled")

    def _marcar_linea_editor(self, linea, tag):
        self.editor.tag_remove("actual", "1.0", "end")
        self.editor.tag_remove("error", "1.0", "end")
        if linea:
            self.editor.tag_add(tag, f"{linea}.0", f"{linea}.end+1c")
            self.editor.see(f"{linea}.0")

    def _aviso(self, texto):
        self.lbl_aviso.configure(text=texto)

    # --- programa en bloques --------------------------------------------------
    PASO_BLOQUE = ALTO_BLOQUE + SEP_BLOQUE

    def _calcular_disposicion(self):
        """Ubica cada pila (funciones primero, como en el código, y luego el programa principal)."""
        pilas = [("fn:" + f["nombre"], f["nombre"], f["cuerpo"]) for f in self.funciones]
        pilas.append(("principal", "", self.principal))
        y, disp = 12, []
        for pila, titulo, cuerpo in pilas:
            y0 = y + ALTO_CABEZA + 8
            fin = y0 + max(1, len(cuerpo)) * self.PASO_BLOQUE
            disp.append({"pila": pila, "titulo": titulo, "cuerpo": cuerpo, "y": y, "y0": y0, "fin": fin})
            y = fin + 22
        self.disposicion = disp
        return y

    def _redibujar_programa(self, resaltado=None, error=False):
        cv = self.cv_prog
        cv.delete("all")
        ancho = max(cv.winfo_width() / self.S, 320)
        total = self._calcular_disposicion()
        y_resaltado = None
        for d in self.disposicion:
            pila, y = d["pila"], d["y"]
            if pila == "principal":
                rect_redondo(cv, 16, y, 220, y + ALTO_CABEZA, r=14, fill="#7c3aed", outline="#a78bfa")
                cv.create_text(30, y + ALTO_CABEZA / 2, text="⚑  al iniciar la misión", anchor="w", fill="white",
                               font=(FUENTE, 11, "bold"))
            else:
                ancho_cab = 120 + 9 * len(d["titulo"])
                rect_redondo(cv, 16, y, 16 + ancho_cab, y + ALTO_CABEZA, r=14, fill=MORADO, outline="#c084fc")
                cv.create_text(30, y + ALTO_CABEZA / 2, text=f"función  {d['titulo']}()", anchor="w", fill="white",
                               font=(FUENTE, 11, "bold"))
                etq = f"delfn_{d['titulo']}"
                cv.create_text(ancho_cab, y + ALTO_CABEZA / 2, text="✕", fill="white", font=(FUENTE, 11, "bold"),
                               tags=(etq,))
                cv.tag_bind(etq, "<Button-1>", lambda e, n=d["titulo"]: self.borrar_funcion(n))
            if not d["cuerpo"]:
                cv.create_text(36, d["y0"] + ALTO_BLOQUE / 2, anchor="w", fill=TEXTO_SUAVE, font=(FUENTE, 10),
                               text=("Arrastra bloques aquí o haz clic en ellos (✕ o clic derecho para borrar)."
                                     if pila == "principal" else "Arrastra aquí los bloques de esta función."))
            for i, clave in enumerate(d["cuerpo"]):
                texto, color, _ = info_bloque(clave)
                yb = d["y0"] + i * self.PASO_BLOQUE
                etiqueta = f"blk|{pila}|{i}"
                borde, grosor = aclarar(color, .35), 1
                if resaltado == (pila, i):
                    borde, grosor = ("#ff5c5c" if error else "#ffffff"), 3
                    y_resaltado = yb
                rect_redondo(cv, 28, yb, ancho - 60, yb + ALTO_BLOQUE, r=10, fill=color, outline=borde,
                             width=grosor, tags=(etiqueta,))
                cv.create_text(40, yb + ALTO_BLOQUE / 2, text=f"{i + 1:>2}", anchor="w", fill=aclarar(color, .6),
                               font=(MONO, 10, "bold"), tags=(etiqueta,))
                cv.create_text(70, yb + ALTO_BLOQUE / 2, text=texto, anchor="w", fill="white",
                               font=(FUENTE, 11, "bold"), tags=(etiqueta,))
                etq_del = f"del|{pila}|{i}"
                cv.create_text(ancho - 78, yb + ALTO_BLOQUE / 2, text="✕", fill="white",
                               font=(FUENTE, 11, "bold"), tags=(etq_del,))
                cv.tag_bind(etq_del, "<Button-1>", lambda e, p=pila, k=i: self._borrar_bloque(p, k))
                cv.tag_bind(etiqueta, "<ButtonPress-1>", lambda e, p=pila, k=i: self._bloque_presionar(e, p, k))
                cv.tag_bind(etiqueta, "<B1-Motion>", self._arrastre_mover)
                cv.tag_bind(etiqueta, "<ButtonRelease-1>", self._arrastre_soltar)
                cv.tag_bind(etiqueta, "<Button-3>", lambda e, p=pila, k=i: self._borrar_bloque(p, k))
        cv.scale("all", 0, 0, self.S, self.S)
        cv.configure(scrollregion=(0, 0, ancho * self.S, (total + 40) * self.S))
        if y_resaltado is not None:
            cv.yview_moveto(max(0, (y_resaltado - 120) / (total + 40)))
        self._redibujar_paleta_funciones()

    def _redibujar_paleta_funciones(self):
        cv = self.cv_funciones
        cv.delete("all")
        for i, f in enumerate(self.funciones):
            clave = "fn:" + f["nombre"]
            texto, color, _ = info_bloque(clave)
            y = 4 + i * (ALTO_BLOQUE + 12)
            etq = f"pal_{clave}"
            rect_redondo(cv, 6, y, 192, y + ALTO_BLOQUE + 2, r=10, fill=color, outline=aclarar(color, .35),
                         width=1, tags=(etq,))
            cv.create_text(20, y + ALTO_BLOQUE / 2 + 1, text=texto, anchor="w", fill="white",
                           font=(FUENTE, 10, "bold"), tags=(etq,))
            cv.tag_bind(etq, "<ButtonPress-1>", lambda e, k=clave: self._paleta_presionar(e, k))
            cv.tag_bind(etq, "<B1-Motion>", self._arrastre_mover)
            cv.tag_bind(etq, "<ButtonRelease-1>", self._arrastre_soltar)
        alto = 4 + len(self.funciones) * (ALTO_BLOQUE + 12)
        cv.configure(height=int(max(1, alto) * self.S))
        cv.scale("all", 0, 0, self.S, self.S)

    def _destino(self, y_canvas):
        """(pila, índice) donde caería un bloque soltado a esa altura del lienzo."""
        y = y_canvas / self.S
        elegido = self.disposicion[-1]
        for d in self.disposicion:
            if y <= d["fin"] + 11:
                elegido = d
                break
        i = round((y - elegido["y0"]) / self.PASO_BLOQUE)
        return elegido["pila"], max(0, min(len(elegido["cuerpo"]), i))

    def _dibujar_marcador(self, pila, indice):
        cv = self.cv_prog
        cv.delete("marcador")
        d = next(d for d in self.disposicion if d["pila"] == pila)
        y = d["y0"] + indice * self.PASO_BLOQUE - SEP_BLOQUE / 2
        cv.create_line(24, y, max(cv.winfo_width() / self.S, 320) - 56, y, fill="#ffffff", width=3, tags=("marcador",))
        cv.scale("marcador", 0, 0, self.S, self.S)

    def _sobre_programa(self, x_raiz, y_raiz):
        cv = self.cv_prog
        x = x_raiz - cv.winfo_rootx()
        y = y_raiz - cv.winfo_rooty()
        dentro = 0 <= x <= cv.winfo_width() and 0 <= y <= cv.winfo_height() and self.vista == "bloques"
        return dentro, cv.canvasy(y)

    def _crear_fantasma(self, clave, x_raiz, y_raiz):
        texto, color, _ = info_bloque(clave)
        g = tk.Toplevel(self.raiz)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.85)
        g.attributes("-topmost", True)
        tk.Label(g, text=texto, bg=color, fg="white", font=(FUENTE, 11, "bold"), padx=14, pady=6).pack()
        g.geometry(f"+{x_raiz - 20}+{y_raiz - 16}")
        return g

    # arrastre: desde la paleta (copia) o desde el programa (mueve / borra)
    def _paleta_presionar(self, e, clave):
        if self.ejecutando:
            return
        self.arrastre = {"origen": "paleta", "clave": clave, "x0": e.x_root, "y0": e.y_root,
                         "fantasma": None, "movido": False}

    def _bloque_presionar(self, e, pila, indice):
        if self.ejecutando:
            return
        self.arrastre = {"origen": "programa", "pila": pila, "indice": indice, "clave": self._lista(pila)[indice],
                         "x0": e.x_root, "y0": e.y_root, "fantasma": None, "movido": False}

    def _arrastre_mover(self, e):
        a = self.arrastre
        if not a:
            return
        if not a["movido"] and abs(e.x_root - a["x0"]) + abs(e.y_root - a["y0"]) > 6:
            a["movido"] = True
            if self.vista != "bloques" and not self._cambiar_vista("bloques"):
                self.arrastre = None
                return
            a["fantasma"] = self._crear_fantasma(a["clave"], e.x_root, e.y_root)
            if a["origen"] == "programa":
                self.cv_prog.itemconfigure(f"blk|{a['pila']}|{a['indice']}", stipple="gray50")
        if a["movido"]:
            a["fantasma"].geometry(f"+{e.x_root - 20}+{e.y_root - 16}")
            dentro, y = self._sobre_programa(e.x_root, e.y_root)
            if dentro:
                self._dibujar_marcador(*self._destino(y))
            else:
                self.cv_prog.delete("marcador")

    def _arrastre_soltar(self, e):
        a, self.arrastre = self.arrastre, None
        if not a:
            return
        if a["fantasma"]:
            a["fantasma"].destroy()
        self.cv_prog.delete("marcador")
        if not a["movido"]:
            if a["origen"] == "paleta":
                self._agregar_bloque(a["clave"])
            return
        dentro, y = self._sobre_programa(e.x_root, e.y_root)
        if a["origen"] == "paleta":
            if dentro:
                self._agregar_bloque(a["clave"], *self._destino(y))
            return
        origen = self._lista(a["pila"])
        clave = origen.pop(a["indice"])
        if dentro:
            pila, destino = self._destino(y)
            if pila == a["pila"] and destino > a["indice"]:
                destino -= 1
            self._lista(pila).insert(destino, clave)
        self._programa_cambiado()

    def _agregar_bloque(self, clave, pila="principal", indice=None):
        if self.vista == "python":
            # en la vista Python el clic agrega la línea al final del texto
            texto = self._texto_editor().rstrip("\n")
            self._poner_texto_editor((texto + "\n" if texto else "") + linea_python(clave))
            self.editor.see("end")
            return
        lista = self._lista(pila)
        if indice is None:
            lista.append(clave)
        else:
            lista.insert(indice, clave)
        self._programa_cambiado()

    def _borrar_bloque(self, pila, indice):
        if self.ejecutando:
            return
        self._lista(pila).pop(indice)
        self._programa_cambiado()

    def crear_funcion(self):
        if self.ejecutando:
            return
        if self.vista == "python" and not self._cambiar_vista("bloques"):
            return
        nombre = simpledialog.askstring("Crear función", "Nombre de la nueva función (por ejemplo: dar_vuelta):",
                                        parent=self.raiz)
        nombre = (nombre or "").strip()
        if not nombre:
            return
        if not nombre.isidentifier():
            self._aviso("Nombre no válido: usa letras, números y _ (sin espacios ni empezar con número).")
            return
        if keyword.iskeyword(nombre) or nombre in FUNCIONES or nombre == "print":
            self._aviso(f"«{nombre}» es una palabra reservada.")
            return
        if any(f["nombre"] == nombre for f in self.funciones):
            self._aviso(f"Ya existe la función {nombre}().")
            return
        self.funciones.append({"nombre": nombre, "cuerpo": []})
        self._aviso("")
        self._programa_cambiado()

    def borrar_funcion(self, nombre):
        if self.ejecutando:
            return
        clave = "fn:" + nombre
        usos = self.principal.count(clave) + sum(f["cuerpo"].count(clave) for f in self.funciones)
        if usos and not messagebox.askyesno("Borrar función",
                                            f"{nombre}() se usa {usos} {'vez' if usos == 1 else 'veces'}. "
                                            "¿Borrar la función y sus llamadas?", parent=self.raiz):
            return
        self.funciones = [f for f in self.funciones if f["nombre"] != nombre]
        self.principal = [k for k in self.principal if k != clave]
        for f in self.funciones:
            f["cuerpo"] = [k for k in f["cuerpo"] if k != clave]
        self._programa_cambiado()

    def _programa_cambiado(self):
        codigo, self.linea_a_bloque = self._codigo_de_bloques()
        self._redibujar_programa()
        self._poner_texto_editor(codigo)

    # --- mapa ---------------------------------------------------------------
    def _centro(self, pos):
        fila, col = pos
        return 30 + (col - 1) * CELDA + CELDA / 2, 30 + (fila - 1) * CELDA + CELDA / 2

    def _dibujar_mapa(self, pos_robot=None, error_en=None):
        cv = self.cv_mapa
        cv.delete("all")
        e = self.sim.estado
        pos_robot = pos_robot or self._centro(e.posicion)
        for c in range(1, COLUMNAS + 1):
            cv.create_text(30 + (c - 1) * CELDA + CELDA / 2, 14, text=str(c), fill=TEXTO_SUAVE, font=(FUENTE, 10, "bold"))
        for f in range(1, FILAS + 1):
            cv.create_text(14, 30 + (f - 1) * CELDA + CELDA / 2, text=str(f), fill=TEXTO_SUAVE, font=(FUENTE, 10, "bold"))
        for f in range(1, FILAS + 1):
            for c in range(1, COLUMNAS + 1):
                x1, y1 = 30 + (c - 1) * CELDA, 30 + (f - 1) * CELDA
                rect_redondo(cv, x1 + 3, y1 + 3, x1 + CELDA - 3, y1 + CELDA - 3, r=12, fill=PANEL_2, outline=BORDE)
        # zona de entrega
        x, y = self._centro(POS_ENTREGA)
        color_entrega = VERDE if e.modulo == ENTREGADO else "#15803d"
        rect_redondo(cv, x - 27, y - 27, x + 27, y + 27, r=10, fill="#0f2f22", outline=color_entrega, width=2, dash=(5, 3))
        cv.create_text(x, y - 21, text="ENTREGA", fill="#86efac", font=(FUENTE, 7, "bold"))
        # obstáculos
        for p in OBSTACULOS:
            x, y = self._centro(p)
            cv.create_polygon(x - 22, y + 8, x - 14, y - 17, x + 3, y - 22, x + 20, y - 9, x + 22, y + 12,
                              x + 5, y + 22, x - 16, y + 19, fill="#4b5068", outline="#71779a", width=2, smooth=True)
            cv.create_oval(x - 10, y - 8, x - 2, y, fill="#3a3e52", outline="")
            cv.create_oval(x + 6, y + 4, x + 16, y + 14, fill="#3a3e52", outline="")
        # rastro
        if len(self.rastro) > 1:
            puntos = [v for p in self.rastro for v in self._centro(p)]
            cv.create_line(*puntos, fill=ACENTO, width=3, dash=(6, 4), capstyle="round")
        # módulo disponible en su celda
        if e.modulo == "disponible":
            x, y = self._centro(POS_MODULO)
            self._dibujar_modulo(x, y - 2, 0.8)
            cv.create_text(x, y + 22, text="MÓDULO", fill="#fcd34d", font=(FUENTE, 7, "bold"))
        elif e.modulo == ENTREGADO:
            x, y = self._centro(POS_ENTREGA)
            self._dibujar_modulo(x, y + 4, 0.7)
        # error
        if error_en:
            x, y = self._centro(error_en) if isinstance(error_en, tuple) and 1 <= error_en[0] <= FILAS \
                and 1 <= error_en[1] <= COLUMNAS else (None, None)
            if x is not None:
                cv.create_oval(x - 27, y - 27, x + 27, y + 27, outline=ROJO, width=4)
        # robot
        self._dibujar_robot(*pos_robot, cargado=(e.modulo == A_BORDO))
        cv.scale("all", 0, 0, self.S, self.S)

    def _dibujar_modulo(self, x, y, s):
        cv = self.cv_mapa
        cv.create_rectangle(x - 12 * s, y - 12 * s, x + 12 * s, y + 12 * s, fill=NARANJA, outline="#fde68a", width=2)
        cv.create_line(x, y - 12 * s, x, y - 22 * s, fill="#fde68a", width=2)
        cv.create_oval(x - 4 * s, y - 26 * s, x + 4 * s, y - 18 * s, fill="#fde68a", outline="")

    def _dibujar_robot(self, x, y, cargado):
        cv = self.cv_mapa
        rect_redondo(cv, x - 18, y - 15, x + 18, y + 19, r=10, fill="#22d3ee", outline="#a5f3fc", width=2)
        cv.create_rectangle(x - 12, y - 8, x + 12, y + 4, fill="#0e3a4a", outline="")
        cv.create_oval(x - 8, y - 5, x - 2, y + 1, fill="#a5f3fc", outline="")
        cv.create_oval(x + 2, y - 5, x + 8, y + 1, fill="#a5f3fc", outline="")
        cv.create_line(x, y - 15, x, y - 21, fill="#a5f3fc", width=2)
        cv.create_oval(x - 3, y - 25, x + 3, y - 19, fill=ROJO, outline="")
        if cargado:
            cv.create_rectangle(x - 7, y + 7, x + 7, y + 16, fill=NARANJA, outline="#fde68a", width=2)

    def _actualizar_estado(self):
        e = self.sim.estado
        self.lbl_pos.configure(text=f"({e.posicion[0]}, {e.posicion[1]})")
        barras = "▮" * e.energia + "▯" * (ENERGIA_INICIAL - e.energia)
        color = VERDE if e.energia > 3 else (NARANJA if e.energia > 0 else ROJO)
        self.lbl_energia.configure(text=f"{e.energia}  {barras}", fg=color)
        colores = {"disponible": TEXTO, A_BORDO: NARANJA, ENTREGADO: VERDE}
        self.lbl_modulo.configure(text=e.modulo, fg=colores[e.modulo])

    def _escribir_registro(self, texto, tag=None):
        self.registro.configure(state="normal")
        self.registro.insert("end", texto + "\n", tag)
        self.registro.see("end")
        self.registro.configure(state="disabled")

    def _limpiar_registro(self):
        self.registro.configure(state="normal")
        self.registro.delete("1.0", "end")
        self.registro.configure(state="disabled")

    def _mostrar_resultado(self, resultado):
        if resultado is None:
            self.lbl_resultado.configure(text="Listo. Arma el programa y pulsa ▶ Ejecutar.", bg=PANEL_2, fg=TEXTO)
            return
        colores = {COMPLETADA: ("#123d26", "#86efac"), INCOMPLETA: ("#3d2f0e", "#fcd34d"),
                   DETENIDA: ("#3d1218", "#fca5a5"), RECHAZADO: ("#3d1218", "#fca5a5")}
        bg, fg = colores[resultado.tipo]
        self.lbl_resultado.configure(text=resultado.mensaje(), bg=bg, fg=fg)

    # --- ejecución animada ----------------------------------------------------
    def _resaltar(self, linea, error=False):
        if self.vista == "bloques":
            self._redibujar_programa(self.linea_a_bloque.get(linea), error=error)
        else:
            self._marcar_linea_editor(linea, "error" if error else "actual")

    def _habilitar(self, ejecutando):
        self.ejecutando = ejecutando
        estado = "disabled" if ejecutando else "normal"
        for b in (self.btn_ejecutar, self.btn_reiniciar, self.btn_limpiar, self.btn_vista_bloques,
                  self.btn_vista_python, self.btn_nueva_funcion):
            b.configure(state=estado)
        self.editor.configure(state=estado)
        self.combo_caso.configure(state="disabled" if ejecutando else "readonly")

    def reiniciar(self):
        self.detener()
        self.sim.reiniciar()
        self.rastro = [self.sim.estado.posicion]
        self._limpiar_registro()
        self._dibujar_mapa()
        self._actualizar_estado()
        self._mostrar_resultado(None)
        self._resaltar(None)

    def ejecutar(self):
        if self.ejecutando:
            return
        if self.vista == "bloques":
            codigo, self.linea_a_bloque = self._codigo_de_bloques()
        else:
            codigo = self._texto_editor()
        self.reiniciar()
        try:
            instrucciones = validar_codigo(codigo)
        except ErrorDeCodigo as e:
            self._escribir_registro(f"Código rechazado — línea {e.linea}: {e.motivo}", "error")
            self._escribir_registro("No se ejecutó ninguna acción.", "error")
            self._resaltar(e.linea, error=True)
            self._mostrar_resultado(Resultado(RECHAZADO, e.linea, e.motivo, self.sim.estado))
            return
        self._escribir_registro(f"Código válido: {len(instrucciones)} acciones.", "ok")
        self._habilitar(True)
        self._paso(instrucciones, 0)

    def _demora(self):
        return int(700 / self.velocidad.get())

    def _paso(self, instrucciones, i):
        if not self.ejecutando:
            return
        if i >= len(instrucciones):
            self._terminar(Resultado(INCOMPLETA, None, "el programa terminó antes de entregar el módulo",
                                     self.sim.estado))
            return
        instr = instrucciones[i]
        self._resaltar(instr.linea)
        origen = self._centro(self.sim.estado.posicion)
        try:
            detalle = self.sim.ejecutar_instruccion(instr)
        except ErrorDeAccion as e:
            self._escribir_registro(f"L{instr.linea}  {instr.como_texto()}{instr.donde()}  ✗ {e.motivo}", "error")
            self._resaltar(instr.linea, error=True)
            destino = None
            if instr.nombre == "mover":
                df, dc = DIRECCIONES[instr.argumentos[0]]
                f, c = self.sim.estado.posicion
                destino = (f + df, c + dc)
            self._dibujar_mapa(error_en=destino or self.sim.estado.posicion)
            self._terminar(Resultado(DETENIDA, instr.linea, e.motivo, self.sim.estado, instr.donde()),
                           resaltar=False)
            return
        self._escribir_registro(f"L{instr.linea}  {detalle}{instr.donde()}", "ok" if instr.nombre != "mover" else None)
        self._actualizar_estado()
        destino = self._centro(self.sim.estado.posicion)
        if instr.nombre == "mover":
            self.rastro.append(self.sim.estado.posicion)

        def siguiente():
            if self.sim.terminado:
                self._terminar(Resultado(COMPLETADA, None, None, self.sim.estado))
            else:
                self.tarea = self.raiz.after(self._demora() // 3, lambda: self._paso(instrucciones, i + 1))

        self._animar(origen, destino, 0, siguiente)

    def _animar(self, origen, destino, k, al_terminar, pasos=10):
        if not self.ejecutando:
            return
        t = k / pasos
        x = origen[0] + (destino[0] - origen[0]) * t
        y = origen[1] + (destino[1] - origen[1]) * t
        self._dibujar_mapa(pos_robot=(x, y))
        if k < pasos:
            self.tarea = self.raiz.after(max(10, self._demora() // pasos),
                                         lambda: self._animar(origen, destino, k + 1, al_terminar, pasos))
        else:
            al_terminar()

    def _terminar(self, resultado, resaltar=True):
        self._habilitar(False)
        self._actualizar_estado()
        self._mostrar_resultado(resultado)
        tag = "ok" if resultado.tipo == COMPLETADA else "error"
        self._escribir_registro(resultado.mensaje(), tag)
        if resaltar and resultado.tipo != DETENIDA:
            self._resaltar(None)

    def detener(self):
        if self.tarea:
            self.raiz.after_cancel(self.tarea)
            self.tarea = None
        if self.ejecutando:
            self._habilitar(False)
            self._escribir_registro("Ejecución detenida por el usuario.", "error")

    def limpiar(self):
        self.reiniciar()
        self.principal, self.funciones = [], []
        self._programa_cambiado()

    def cargar_caso(self):
        nombre = self.combo_caso.get()
        for titulo, lineas, esperado, _ in CASOS:
            if titulo == nombre:
                self.reiniciar()
                self._poner_texto_editor("\n".join(lineas))
                if self.vista == "bloques":
                    # un caso con código inválido (por ejemplo el 6) solo se puede ver en Python
                    self.vista = "python"
                    if not self._cambiar_vista("bloques"):
                        self._cambiar_vista("python")
                        self._aviso("Este caso contiene código inválido: se muestra en la vista Python.")
                self._escribir_registro(f"Caso cargado: {nombre}")
                self._escribir_registro(f"Esperado: {esperado}")
                return


def iniciar_interfaz():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    iniciar_interfaz()

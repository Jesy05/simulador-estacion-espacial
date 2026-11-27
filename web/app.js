// Versión web del simulador.
// Toda la lógica (validación con ast, funciones propias, reglas, mensajes) es la de
// simulador.py, que se ejecuta con Python 3 dentro del navegador gracias a Pyodide.
// Este archivo solo dibuja la interfaz: bloques, editor, mapa y registro.

const PRIMITIVOS = {
  norte:    { texto: "mover ↑ norte",   tipo: "mover",    linea: 'mover("norte")' },
  sur:      { texto: "mover ↓ sur",     tipo: "mover",    linea: 'mover("sur")' },
  este:     { texto: "mover → este",    tipo: "mover",    linea: 'mover("este")' },
  oeste:    { texto: "mover ← oeste",   tipo: "mover",    linea: 'mover("oeste")' },
  recoger:  { texto: "recoger módulo",  tipo: "recoger",  linea: "recoger()" },
  entregar: { texto: "entregar módulo", tipo: "entregar", linea: "entregar()" },
};

// Un bloque se guarda como una "clave": "este", "recoger"... o "fn:nombre" para llamar a una función propia.
function infoBloque(clave) {
  if (clave.startsWith("fn:")) {
    const nombre = clave.slice(3);
    return { texto: `llamar ${nombre}()`, tipo: "llamada", linea: `${nombre}()` };
  }
  return PRIMITIVOS[clave];
}

const PUENTE_PY = `
import json
import simulador as s
import pruebas

sim = s.Simulador()
_instr = []

def info():
    return json.dumps({
        "filas": s.FILAS, "columnas": s.COLUMNAS, "inicio": list(s.INICIO),
        "modulo": list(s.POS_MODULO), "entrega": list(s.POS_ENTREGA),
        "obstaculos": [list(p) for p in sorted(s.OBSTACULOS)], "energia": s.ENERGIA_INICIAL,
        "casos": [{"nombre": n, "codigo": "\\n".join(c), "esperado": e} for n, c, e, _ in pruebas.TODOS],
    })

def estado():
    e = sim.estado
    return {"pos": list(e.posicion), "energia": e.energia, "modulo": e.modulo}

def _llamadas(lista):
    return [{"nombre": l.nombre, "args": list(l.argumentos), "linea": l.linea} for l in lista]

def estructura(codigo):
    try:
        p = s.analizar_programa(codigo)
    except s.ErrorDeCodigo as e:
        return json.dumps({"ok": False, "linea": e.linea, "motivo": e.motivo})
    return json.dumps({"ok": True,
        "funciones": [{"nombre": f.nombre, "linea": f.linea, "llamadas": _llamadas(f.llamadas)}
                      for f in p.funciones.values()],
        "principal": _llamadas(p.principal)})

def preparar(codigo):
    global _instr
    sim.reiniciar()
    try:
        _instr = s.validar_codigo(codigo)
    except s.ErrorDeCodigo as e:
        r = s.Resultado(s.RECHAZADO, e.linea, e.motivo, sim.estado)
        return json.dumps({"ok": False, "linea": e.linea, "motivo": e.motivo, "mensaje": r.mensaje()})
    return json.dumps({"ok": True, "instr": [
        {"linea": i.linea, "nombre": i.nombre, "args": list(i.argumentos), "texto": i.como_texto(),
         "donde": i.donde(), "llamadas": [l for _, l in i.pila]}
        for i in _instr]})

def paso(k):
    i = _instr[k]
    try:
        detalle = sim.ejecutar_instruccion(i)
    except s.ErrorDeAccion as e:
        r = s.Resultado(s.DETENIDA, i.linea, e.motivo, sim.estado, i.donde())
        return json.dumps({"ok": False, "motivo": e.motivo, "mensaje": r.mensaje(), "estado": estado()})
    out = {"ok": True, "detalle": detalle, "estado": estado(), "terminado": sim.terminado}
    if sim.terminado:
        out["mensaje"] = s.Resultado(s.COMPLETADA, None, None, sim.estado).mensaje()
    return json.dumps(out)

def incompleta():
    return s.Resultado(s.INCOMPLETA, None, "el programa terminó antes de entregar el módulo", sim.estado).mensaje()

def reiniciar():
    sim.reiniciar()
    return json.dumps(estado())
`;

const PALABRAS_RESERVADAS = new Set(("False None True and as assert async await break class continue def del elif " +
  "else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield " +
  "mover recoger entregar print").split(" "));

const $ = (sel) => document.querySelector(sel);
const app = {
  py: null, info: null,
  prog: { funciones: [], principal: [] },   // funciones: [{nombre, cuerpo: [claves]}]
  vista: "bloques", ejecutando: false, temporizador: null, rastro: [],
  lineaABloque: {},                          // línea de código -> [pila, índice]
};

// ---------------------------------------------------------------------------
// Arranque: cargar Pyodide y los archivos .py del repositorio
// ---------------------------------------------------------------------------
async function iniciar() {
  construirPaleta();
  enlazarEventos();
  renderPrograma();
  try {
    const py = await loadPyodide();
    for (const archivo of ["simulador.py", "pruebas.py"]) {
      const texto = await (await fetch(archivo + "?v=" + Date.now(), { cache: "no-cache" })).text();
      py.FS.writeFile(archivo, texto);
    }
    py.runPython("import sys; sys.path.insert(0, '.')");
    py.runPython(PUENTE_PY);
    app.py = py;
    app.info = JSON.parse(py.globals.get("info")());
    const selector = $("#caso");
    app.info.casos.forEach((c, i) => selector.add(new Option(c.nombre, i)));
    const pildora = $("#estado-python");
    pildora.textContent = "Python " + py.runPython("import sys; sys.version.split()[0]") + " listo";
    pildora.className = "pildora listo";
    $("#btn-ejecutar").disabled = false;
    reiniciar();
  } catch (err) {
    console.error(err);
    const pildora = $("#estado-python");
    pildora.textContent = "No se pudo cargar Python";
    pildora.className = "pildora error";
    mostrarResultado("detenida", "No se pudo cargar el intérprete de Python. Revisa tu conexión y recarga la página.");
  }
}

function llamarPy(nombre, ...args) {
  return JSON.parse(app.py.globals.get(nombre)(...args));
}

// ---------------------------------------------------------------------------
// Modelo de bloques: pilas "principal" y "fn:nombre"
// ---------------------------------------------------------------------------
function listaDe(pila) {
  if (pila === "principal") return app.prog.principal;
  const f = app.prog.funciones.find((f) => "fn:" + f.nombre === pila);
  return f ? f.cuerpo : null;
}

function codigoDeBloques() {
  // Genera el código Python y, de paso, qué línea corresponde a cada bloque.
  const lineas = [], mapa = {};
  for (const f of app.prog.funciones) {
    lineas.push(`def ${f.nombre}():`);
    if (!f.cuerpo.length) lineas.push("    pass");
    f.cuerpo.forEach((clave, i) => {
      lineas.push("    " + infoBloque(clave).linea);
      mapa[lineas.length] = ["fn:" + f.nombre, i];
    });
    lineas.push("");
  }
  app.prog.principal.forEach((clave, i) => {
    lineas.push(infoBloque(clave).linea);
    mapa[lineas.length] = ["principal", i];
  });
  return { codigo: lineas.join("\n").replace(/\n+$/, ""), mapa };
}

function claveDeLlamada(l) {
  if (l.nombre === "mover") return l.args[0];
  if (l.nombre === "recoger" || l.nombre === "entregar") return l.nombre;
  return "fn:" + l.nombre;
}

function programaDesdeCodigo(codigo) {
  // Usa analizar_programa de simulador.py para pasar de Python a bloques.
  const r = llamarPy("estructura", codigo);
  if (!r.ok) return r;
  const mapa = {};
  app.prog = {
    funciones: r.funciones.map((f) => ({
      nombre: f.nombre,
      cuerpo: f.llamadas.map((l, i) => { mapa[l.linea] = ["fn:" + f.nombre, i]; return claveDeLlamada(l); }),
    })),
    principal: r.principal.map((l, i) => { mapa[l.linea] = ["principal", i]; return claveDeLlamada(l); }),
  };
  app.lineaABloque = mapa;
  return r;
}

// ---------------------------------------------------------------------------
// Bloques (DOM)
// ---------------------------------------------------------------------------
function crearBloque(clave, pila, indice) {
  const b = infoBloque(clave);
  const enPrograma = pila !== undefined;
  const el = document.createElement(enPrograma ? "li" : "div");
  el.className = `blk ${b.tipo}`;
  el.draggable = true;
  el.dataset.clave = clave;
  if (enPrograma) {
    el.innerHTML = `<span class="num">${indice + 1}</span><span class="txt">${b.texto}</span>` +
                   `<button class="borrar" title="Borrar bloque" aria-label="Borrar bloque">✕</button>`;
  } else {
    el.innerHTML = `<span class="txt">${b.texto}</span>`;
  }
  return el;
}

function bloqueDePaleta(clave) {
  const el = crearBloque(clave);
  el.addEventListener("click", () => agregarBloque(clave));
  el.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", JSON.stringify({ origen: "paleta", clave }));
    e.dataTransfer.effectAllowed = "copy";
  });
  return el;
}

function construirPaleta() {
  const lista = $("#lista-paleta");
  for (const clave of Object.keys(PRIMITIVOS)) lista.appendChild(bloqueDePaleta(clave));
}

function renderPaletaFunciones() {
  const lista = $("#lista-funciones");
  lista.innerHTML = "";
  for (const f of app.prog.funciones) lista.appendChild(bloqueDePaleta("fn:" + f.nombre));
}

function crearPila(pila, titulo, cuerpo, resaltado, error) {
  const sec = document.createElement("section");
  sec.className = "pila";
  sec.dataset.pila = pila;
  const cab = document.createElement("div");
  if (pila === "principal") {
    cab.className = "sombrero";
    cab.textContent = "⚑ al iniciar la misión";
  } else {
    cab.className = "sombrero funcion";
    cab.innerHTML = `<span>función <code>${titulo}()</code></span>` +
                    `<button class="borrar-fn" title="Borrar función" aria-label="Borrar función">✕</button>`;
    cab.querySelector(".borrar-fn").addEventListener("click", () => borrarFuncion(titulo));
  }
  sec.appendChild(cab);
  const ol = document.createElement("ol");
  ol.className = "programa";
  cuerpo.forEach((clave, i) => {
    const el = crearBloque(clave, pila, i);
    if (resaltado && resaltado[0] === pila && resaltado[1] === i) el.classList.add(error ? "error" : "actual");
    el.querySelector(".borrar").addEventListener("click", (e) => { e.stopPropagation(); borrarBloque(pila, i); });
    el.addEventListener("dragstart", (e) => {
      if (app.ejecutando) { e.preventDefault(); return; }
      e.dataTransfer.setData("text/plain", JSON.stringify({ origen: "programa", pila, indice: i }));
      e.dataTransfer.effectAllowed = "move";
      requestAnimationFrame(() => el.classList.add("arrastrando"));
    });
    el.addEventListener("dragend", () => el.classList.remove("arrastrando"));
    ol.appendChild(el);
  });
  sec.appendChild(ol);
  if (!cuerpo.length) {
    const p = document.createElement("p");
    p.className = "suave vacio";
    p.innerHTML = pila === "principal"
      ? "Arrastra bloques aquí o haz clic en ellos.<br>Arrastra un bloque fuera para borrarlo (o pulsa ✕)."
      : "Arrastra aquí los bloques de esta función.";
    sec.appendChild(p);
  }
  return sec;
}

function renderPrograma(resaltado = null, error = false) {
  const cont = $("#pilas");
  cont.innerHTML = "";
  for (const f of app.prog.funciones)
    cont.appendChild(crearPila("fn:" + f.nombre, f.nombre, f.cuerpo, resaltado, error));
  cont.appendChild(crearPila("principal", "", app.prog.principal, resaltado, error));
  renderPaletaFunciones();
  if (resaltado) cont.querySelector(".blk.actual, .blk.error")?.scrollIntoView({ block: "nearest" });
}

function pilaBajo(elemento) {
  const sec = elemento.closest?.(".pila");
  return sec ? sec.dataset.pila : null;
}

function indiceInsercion(pila, y) {
  const sec = document.querySelector(`.pila[data-pila="${CSS.escape(pila)}"]`);
  const items = [...sec.querySelectorAll(".blk")];
  for (let i = 0; i < items.length; i++) {
    const r = items[i].getBoundingClientRect();
    if (y < r.top + r.height / 2) return i;
  }
  return items.length;
}

function mostrarMarcador(pila, indice) {
  quitarMarcador();
  const sec = document.querySelector(`.pila[data-pila="${CSS.escape(pila)}"]`);
  sec.classList.add("activa-destino");
  const ol = sec.querySelector("ol");
  const m = document.createElement("li");
  m.className = "marcador";
  ol.insertBefore(m, ol.querySelectorAll(".blk")[indice] || null);
}
function quitarMarcador() {
  document.querySelectorAll(".marcador").forEach((m) => m.remove());
  document.querySelectorAll(".activa-destino").forEach((s) => s.classList.remove("activa-destino"));
}

function agregarBloque(clave, pila = "principal", indice) {
  if (app.ejecutando) return;
  if (app.vista === "python") {
    const t = $("#codigo").value.replace(/\n+$/, "");
    ponerCodigo((t ? t + "\n" : "") + infoBloque(clave).linea);
    return;
  }
  const lista = listaDe(pila);
  if (indice === undefined) lista.push(clave);
  else lista.splice(indice, 0, clave);
  programaCambiado();
}

function borrarBloque(pila, i) {
  if (app.ejecutando) return;
  listaDe(pila).splice(i, 1);
  programaCambiado();
}

function moverBloque(desde, i, hacia, destino) {
  const origen = listaDe(desde);
  const [clave] = origen.splice(i, 1);
  if (desde === hacia && destino > i) destino -= 1;
  listaDe(hacia).splice(destino, 0, clave);
  programaCambiado();
}

function crearFuncion() {
  if (app.ejecutando) return;
  if (app.vista === "python" && !cambiarVista("bloques")) return;
  const nombre = (prompt("Nombre de la nueva función (por ejemplo: dar_vuelta)", "") || "").trim();
  if (!nombre) return;
  if (!/^[A-Za-z_áéíóúñÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ]*$/.test(nombre)) return aviso("Nombre no válido: usa letras, números y _ (sin espacios).");
  if (PALABRAS_RESERVADAS.has(nombre)) return aviso(`«${nombre}» es una palabra reservada.`);
  if (app.prog.funciones.some((f) => f.nombre === nombre)) return aviso(`Ya existe la función ${nombre}().`);
  app.prog.funciones.push({ nombre, cuerpo: [] });
  aviso("");
  programaCambiado();
}

function borrarFuncion(nombre) {
  if (app.ejecutando) return;
  const usos = [app.prog.principal, ...app.prog.funciones.map((f) => f.cuerpo)]
    .reduce((n, l) => n + l.filter((k) => k === "fn:" + nombre).length, 0);
  if (usos && !confirm(`${nombre}() se usa ${usos} ${usos === 1 ? "vez" : "veces"}. ¿Borrar la función y sus llamadas?`)) return;
  app.prog.funciones = app.prog.funciones.filter((f) => f.nombre !== nombre);
  const quitar = (l) => l.filter((k) => k !== "fn:" + nombre);
  app.prog.principal = quitar(app.prog.principal);
  app.prog.funciones.forEach((f) => { f.cuerpo = quitar(f.cuerpo); });
  programaCambiado();
}

function programaCambiado() {
  const { codigo, mapa } = codigoDeBloques();
  app.lineaABloque = mapa;
  renderPrograma();
  ponerCodigo(codigo);
}

// ---------------------------------------------------------------------------
// Editor de Python (textarea transparente sobre un fondo coloreado)
// ---------------------------------------------------------------------------
function escapar(t) { return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function pintarEditor(lineaMarcada = null, tipo = "actual") {
  const lineas = $("#codigo").value.split("\n");
  $("#resaltado").innerHTML = lineas.map((l, i) => {
    let h = escapar(l);
    const com = h.indexOf("#");
    let comentario = "";
    if (com >= 0 && !/"[^"]*#/.test(h.slice(0, com + 1))) { comentario = h.slice(com); h = h.slice(0, com); }
    h = h.replace(/("""[^"]*"""|"[^"]*")/g, (m) => `<span class="str">${m}</span>`)
         .replace(/\b(def|pass)\b/g, '<span class="kw">$1</span>')
         .replace(/\b(mover|recoger|entregar)\b(?=\()/g, '<span class="fn">$1</span>');
    if (comentario) h += `<span class="com">${comentario}</span>`;
    const cls = lineaMarcada === i + 1 ? ` ${tipo}` : "";
    return `<span class="linea${cls}">${h || " "}</span>`;
  }).join("");
  $("#numeros").textContent = lineas.map((_, i) => i + 1).join("\n");
  sincronizarScroll();
}

function sincronizarScroll() {
  const ta = $("#codigo");
  $("#resaltado").scrollTop = ta.scrollTop;
  $("#resaltado").scrollLeft = ta.scrollLeft;
  $("#numeros").scrollTop = ta.scrollTop;
}

function ponerCodigo(texto) { $("#codigo").value = texto; pintarEditor(); }

// ---------------------------------------------------------------------------
// Vistas
// ---------------------------------------------------------------------------
function aviso(t) { $("#aviso").textContent = t; }

function cambiarVista(vista) {
  if (vista === app.vista) return true;
  if (vista === "bloques") {
    if (!app.py) return false;
    const r = programaDesdeCodigo($("#codigo").value);
    if (!r.ok) {
      aviso(`No se puede pasar a bloques — línea ${r.linea}: ${r.motivo}`);
      pintarEditor(r.linea, "error");
      return false;
    }
  } else {
    ponerCodigo(codigoDeBloques().codigo);
  }
  mostrarVista(vista);
  return true;
}

function mostrarVista(vista) {
  // solo cambia lo que se ve; no toca el programa ni el código
  app.vista = vista;
  aviso("");
  $("#vista-bloques").hidden = vista !== "bloques";
  $("#vista-python").hidden = vista !== "python";
  $("#tab-bloques").classList.toggle("activa", vista === "bloques");
  $("#tab-python").classList.toggle("activa", vista === "python");
  if (vista === "bloques") renderPrograma(); else { pintarEditor(); $("#codigo").focus(); }
}

function resaltar(linea, error = false) {
  if (app.vista === "bloques") renderPrograma(linea == null ? null : app.lineaABloque[linea] || null, error);
  else pintarEditor(linea, error ? "error" : "actual");
}

// ---------------------------------------------------------------------------
// Mapa (SVG)
// ---------------------------------------------------------------------------
const CELDA = 64, MARGEN = 32;
const centro = ([f, c]) => [MARGEN + (c - 1) * CELDA + CELDA / 2, MARGEN + (f - 1) * CELDA + CELDA / 2];
const dentro = ([f, c]) => app.info && f >= 1 && f <= app.info.filas && c >= 1 && c <= app.info.columnas;

function svg(tag, attrs, padre) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (padre) padre.appendChild(el);
  return el;
}

function dibujarModulo(g, x, y, s) {
  svg("line", { x1: x, y1: y - 11 * s, x2: x, y2: y - 20 * s, stroke: "#fde68a", "stroke-width": 2 }, g);
  svg("circle", { cx: x, cy: y - 22 * s, r: 3.5 * s, fill: "#fde68a" }, g);
  svg("rect", { x: x - 11 * s, y: y - 11 * s, width: 22 * s, height: 22 * s, rx: 3, fill: "#f59e0b", stroke: "#fde68a", "stroke-width": 2 }, g);
}

function dibujarMapa(estado, errorEn = null) {
  const m = $("#mapa");
  const inf = app.info;
  m.innerHTML = "";
  if (!inf) return;
  for (let c = 1; c <= inf.columnas; c++)
    svg("text", { x: MARGEN + (c - 1) * CELDA + CELDA / 2, y: 20, fill: "#93a0c8", "font-size": 13, "font-weight": 700, "text-anchor": "middle" }, m).textContent = c;
  for (let f = 1; f <= inf.filas; f++)
    svg("text", { x: 14, y: MARGEN + (f - 1) * CELDA + CELDA / 2 + 5, fill: "#93a0c8", "font-size": 13, "font-weight": 700, "text-anchor": "middle" }, m).textContent = f;
  for (let f = 1; f <= inf.filas; f++)
    for (let c = 1; c <= inf.columnas; c++)
      svg("rect", { x: MARGEN + (c - 1) * CELDA + 3, y: MARGEN + (f - 1) * CELDA + 3, width: CELDA - 6, height: CELDA - 6, rx: 10, fill: "#1b2546", stroke: "#2a3766" }, m);

  let [x, y] = centro(inf.entrega);
  svg("rect", { x: x - 27, y: y - 27, width: 54, height: 54, rx: 9, fill: "#0f2f22",
                stroke: estado.modulo === "entregado" ? "#22c55e" : "#15803d", "stroke-width": 2, "stroke-dasharray": "5 3" }, m);
  svg("text", { x, y: y - 16, fill: "#86efac", "font-size": 8, "font-weight": 800, "text-anchor": "middle" }, m).textContent = "ENTREGA";

  for (const p of inf.obstaculos) {
    [x, y] = centro(p);
    const g = svg("g", { transform: `translate(${x} ${y})` }, m);
    svg("path", { d: "M-22 6 Q-20 -16 -4 -21 Q16 -22 21 -6 Q25 12 6 21 Q-14 25 -22 6Z", fill: "#4b5068", stroke: "#71779a", "stroke-width": 2 }, g);
    svg("circle", { cx: -7, cy: -5, r: 4, fill: "#3a3e52" }, g);
    svg("circle", { cx: 9, cy: 8, r: 5, fill: "#3a3e52" }, g);
  }

  if (app.rastro.length > 1)
    svg("polyline", { points: app.rastro.map((p) => centro(p).join(",")).join(" "), fill: "none",
                      stroke: "#5b8cff", "stroke-width": 3, "stroke-dasharray": "6 5", "stroke-linecap": "round" }, m);

  if (estado.modulo === "disponible") {
    [x, y] = centro(inf.modulo);
    dibujarModulo(m, x, y - 2, 0.85);
    svg("text", { x, y: y + 22, fill: "#fcd34d", "font-size": 8, "font-weight": 800, "text-anchor": "middle" }, m).textContent = "MÓDULO";
  } else if (estado.modulo === "entregado") {
    [x, y] = centro(inf.entrega);
    dibujarModulo(m, x, y + 6, 0.65);
  }

  if (errorEn && dentro(errorEn)) {
    [x, y] = centro(errorEn);
    svg("circle", { cx: x, cy: y, r: 27, fill: "none", stroke: "#ef4444", "stroke-width": 4 }, m);
  }

  [x, y] = centro(estado.pos);
  const r = svg("g", { class: "robot", style: `transform: translate(${x}px, ${y}px)` }, m);
  svg("rect", { x: -18, y: -15, width: 36, height: 34, rx: 9, fill: "#22d3ee", stroke: "#a5f3fc", "stroke-width": 2 }, r);
  svg("rect", { x: -12, y: -8, width: 24, height: 12, rx: 3, fill: "#0e3a4a" }, r);
  svg("circle", { cx: -5, cy: -2, r: 3, fill: "#a5f3fc" }, r);
  svg("circle", { cx: 5, cy: -2, r: 3, fill: "#a5f3fc" }, r);
  svg("line", { x1: 0, y1: -15, x2: 0, y2: -21, stroke: "#a5f3fc", "stroke-width": 2 }, r);
  svg("circle", { cx: 0, cy: -23, r: 3, fill: "#ef4444" }, r);
  if (estado.modulo === "a bordo")
    svg("rect", { x: -7, y: 7, width: 14, height: 9, rx: 2, fill: "#f59e0b", stroke: "#fde68a", "stroke-width": 2 }, r);
  app.robot = r;
}

function moverRobot(estado, ms) {
  if (!app.robot) return dibujarMapa(estado);
  const [x, y] = centro(estado.pos);
  app.robot.style.setProperty("--dur", ms + "ms");
  app.robot.getBoundingClientRect();
  app.robot.style.transform = `translate(${x}px, ${y}px)`;
}

function actualizarIndicadores(e) {
  $("#ind-pos").textContent = `(${e.pos[0]}, ${e.pos[1]})`;
  const total = app.info ? app.info.energia : 8;
  const ind = $("#ind-energia");
  ind.textContent = `${e.energia} ${"▮".repeat(e.energia)}${"▯".repeat(Math.max(0, total - e.energia))}`;
  ind.style.color = e.energia > 3 ? "#22c55e" : e.energia > 0 ? "#f59e0b" : "#ef4444";
  const mod = $("#ind-modulo");
  mod.textContent = e.modulo;
  mod.style.color = { "disponible": "#e6ebff", "a bordo": "#f59e0b", "entregado": "#22c55e" }[e.modulo];
}

// ---------------------------------------------------------------------------
// Registro y resultado
// ---------------------------------------------------------------------------
function registrar(texto, tipo = "") {
  const div = document.createElement("div");
  if (tipo) div.className = tipo;
  div.textContent = texto;
  const r = $("#registro");
  r.appendChild(div);
  r.scrollTop = r.scrollHeight;
}

function mostrarResultado(tipo, texto) {
  const r = $("#resultado");
  r.className = "resultado" + (tipo ? " " + tipo : "");
  r.textContent = texto;
}

// ---------------------------------------------------------------------------
// Ejecución
// ---------------------------------------------------------------------------
function demora() { return Math.round(700 / Number($("#velocidad").value)); }

function habilitar(ejecutando) {
  app.ejecutando = ejecutando;
  for (const id of ["#btn-ejecutar", "#btn-reiniciar", "#btn-borrar", "#tab-bloques", "#tab-python", "#caso", "#btn-nueva-funcion"])
    $(id).disabled = ejecutando;
  $("#codigo").readOnly = ejecutando;
}

function reiniciar() {
  detener(true);
  if (!app.py) return;
  const e = llamarPy("reiniciar");
  app.rastro = [e.pos];
  $("#registro").innerHTML = "";
  dibujarMapa(e);
  actualizarIndicadores(e);
  mostrarResultado("", "Listo. Arma el programa y pulsa ▶ Ejecutar.");
  resaltar(null);
}

function ejecutar() {
  if (app.ejecutando || !app.py) return;
  let codigo;
  if (app.vista === "bloques") {
    const g = codigoDeBloques();
    codigo = g.codigo;
    app.lineaABloque = g.mapa;
  } else {
    codigo = $("#codigo").value;
  }
  reiniciar();
  const r = llamarPy("preparar", codigo);
  if (!r.ok) {
    registrar(`Código rechazado — línea ${r.linea}: ${r.motivo}`, "error");
    registrar("No se ejecutó ninguna acción.", "error");
    resaltar(r.linea, true);
    mostrarResultado("detenida", r.mensaje);
    return;
  }
  registrar(`Código válido: ${r.instr.length} acciones.`, "ok");
  habilitar(true);
  paso(r.instr, 0);
}

function paso(instr, k) {
  if (!app.ejecutando) return;
  if (k >= instr.length) return terminar("incompleta", app.py.globals.get("incompleta")());
  const i = instr[k];
  resaltar(i.linea);
  const r = llamarPy("paso", k);
  if (!r.ok) {
    registrar(`L${i.linea}  ${i.texto}${i.donde}  ✗ ${r.motivo}`, "error");
    resaltar(i.linea, true);
    let destino = r.estado.pos;
    if (i.nombre === "mover") {
      const d = { norte: [-1, 0], sur: [1, 0], oeste: [0, -1], este: [0, 1] }[i.args[0]];
      destino = [r.estado.pos[0] + d[0], r.estado.pos[1] + d[1]];
    }
    dibujarMapa(r.estado, destino);
    return terminar("detenida", r.mensaje, false);
  }
  registrar(`L${i.linea}  ${r.detalle}${i.donde}`, i.nombre === "mover" ? "" : "ok");
  actualizarIndicadores(r.estado);
  const ms = demora();
  if (i.nombre === "mover") {
    app.rastro.push(r.estado.pos);
    moverRobot(r.estado, ms);
  }
  app.temporizador = setTimeout(() => {
    dibujarMapa(r.estado);
    if (r.terminado) return terminar("completada", r.mensaje);
    app.temporizador = setTimeout(() => paso(instr, k + 1), ms / 3);
  }, i.nombre === "mover" ? ms : ms / 2);
}

function terminar(tipo, mensaje, limpiarResaltado = true) {
  habilitar(false);
  mostrarResultado(tipo, mensaje);
  registrar(mensaje, tipo === "completada" ? "ok" : "error");
  if (limpiarResaltado) resaltar(null);
}

function detener(silencioso = false) {
  clearTimeout(app.temporizador);
  if (app.ejecutando) {
    habilitar(false);
    if (!silencioso) registrar("Ejecución detenida por el usuario.", "error");
  }
}

function cargarCaso() {
  const idx = $("#caso").value;
  if (idx === "") return;
  const caso = app.info.casos[idx];
  reiniciar();
  ponerCodigo(caso.codigo);
  if (app.vista === "bloques") {
    app.vista = "python";              // el código viene como texto: se convierte a bloques si es válido
    if (!cambiarVista("bloques")) {
      mostrarVista("python");
      aviso("Este caso contiene código inválido: se muestra en la vista Python.");
    }
  }
  registrar(`Caso cargado: ${caso.nombre}`);
  registrar(`Esperado: ${caso.esperado}`);
}

// ---------------------------------------------------------------------------
// Eventos
// ---------------------------------------------------------------------------
function enlazarEventos() {
  $("#tab-bloques").addEventListener("click", () => cambiarVista("bloques"));
  $("#tab-python").addEventListener("click", () => cambiarVista("python"));
  $("#btn-ejecutar").addEventListener("click", ejecutar);
  $("#btn-detener").addEventListener("click", () => detener());
  $("#btn-reiniciar").addEventListener("click", reiniciar);
  $("#btn-nueva-funcion").addEventListener("click", crearFuncion);
  $("#btn-borrar").addEventListener("click", () => {
    reiniciar();
    app.prog = { funciones: [], principal: [] };
    programaCambiado();
  });
  $("#caso").addEventListener("change", cargarCaso);

  const ta = $("#codigo");
  ta.addEventListener("input", () => pintarEditor());
  ta.addEventListener("scroll", sincronizarScroll);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      ta.setRangeText("    ", ta.selectionStart, ta.selectionEnd, "end");
      pintarEditor();
    }
  });

  // arrastrar y soltar en las pilas (programa principal y funciones)
  const zona = $("#vista-bloques");
  const pilaDestino = (e) => pilaBajo(e.target) || "principal";
  zona.addEventListener("dragover", (e) => {
    e.preventDefault();
    const pila = pilaDestino(e);
    mostrarMarcador(pila, indiceInsercion(pila, e.clientY));
  });
  zona.addEventListener("dragleave", (e) => { if (!zona.contains(e.relatedTarget)) quitarMarcador(); });
  zona.addEventListener("drop", (e) => {
    e.preventDefault();
    quitarMarcador();
    let datos;
    try { datos = JSON.parse(e.dataTransfer.getData("text/plain")); } catch { return; }
    const pila = pilaDestino(e);
    const destino = indiceInsercion(pila, e.clientY);
    if (datos.origen === "paleta") return agregarBloque(datos.clave, pila, destino);
    moverBloque(datos.pila, datos.indice, pila, destino);
  });
  // soltar un bloque del programa fuera de la zona = borrarlo
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => {
    if (zona.contains(e.target)) return;
    e.preventDefault();
    quitarMarcador();
    try {
      const datos = JSON.parse(e.dataTransfer.getData("text/plain"));
      if (datos.origen === "programa") borrarBloque(datos.pila, datos.indice);
    } catch { /* no era un bloque */ }
  });
}

iniciar();

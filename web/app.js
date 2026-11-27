// Versión web del simulador.
// Toda la lógica (validación con ast, reglas, mensajes) es la de simulador.py,
// que se ejecuta con Python 3 dentro del navegador gracias a Pyodide.
// Este archivo solo dibuja la interfaz: bloques, editor, mapa y registro.

const BLOQUES = {
  norte:    { texto: "mover ↑ norte",     tipo: "mover",    linea: 'mover("norte")' },
  sur:      { texto: "mover ↓ sur",       tipo: "mover",    linea: 'mover("sur")' },
  este:     { texto: "mover → este",      tipo: "mover",    linea: 'mover("este")' },
  oeste:    { texto: "mover ← oeste",     tipo: "mover",    linea: 'mover("oeste")' },
  recoger:  { texto: "recoger módulo",    tipo: "recoger",  linea: "recoger()" },
  entregar: { texto: "entregar módulo",   tipo: "entregar", linea: "entregar()" },
};

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
        "casos": [{"nombre": n, "codigo": "\\n".join(c), "esperado": e} for n, c, e, _ in pruebas.CASOS],
    })

def estado():
    e = sim.estado
    return {"pos": list(e.posicion), "energia": e.energia, "modulo": e.modulo}

def preparar(codigo):
    global _instr
    sim.reiniciar()
    try:
        _instr = s.validar_codigo(codigo)
    except s.ErrorDeCodigo as e:
        r = s.Resultado(s.RECHAZADO, e.linea, e.motivo, sim.estado)
        return json.dumps({"ok": False, "linea": e.linea, "motivo": e.motivo, "mensaje": r.mensaje()})
    return json.dumps({"ok": True, "instr": [
        {"linea": i.linea, "nombre": i.nombre, "args": list(i.argumentos), "texto": i.como_texto()}
        for i in _instr]})

def paso(k):
    i = _instr[k]
    try:
        detalle = sim.ejecutar_instruccion(i)
    except s.ErrorDeAccion as e:
        r = s.Resultado(s.DETENIDA, i.linea, e.motivo, sim.estado)
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

const $ = (sel) => document.querySelector(sel);
const app = {
  py: null, info: null, programa: [], vista: "bloques",
  ejecutando: false, temporizador: null, rastro: [], lineaABloque: {},
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
      const texto = await (await fetch(archivo, { cache: "no-cache" })).text();
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
// Bloques
// ---------------------------------------------------------------------------
function crearBloque(clave, indice) {
  const b = BLOQUES[clave];
  const el = document.createElement(indice === undefined ? "div" : "li");
  el.className = `blk ${b.tipo}`;
  el.draggable = true;
  el.dataset.clave = clave;
  if (indice !== undefined) {
    el.dataset.indice = indice;
    el.innerHTML = `<span class="num">${indice + 1}</span><span class="txt">${b.texto}</span>` +
                   `<button class="borrar" title="Borrar bloque" aria-label="Borrar bloque">✕</button>`;
  } else {
    el.innerHTML = `<span class="txt">${b.texto}</span>`;
  }
  return el;
}

function construirPaleta() {
  const lista = $("#lista-paleta");
  for (const clave of Object.keys(BLOQUES)) {
    const el = crearBloque(clave);
    el.addEventListener("click", () => agregarBloque(clave));
    el.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", JSON.stringify({ origen: "paleta", clave }));
      e.dataTransfer.effectAllowed = "copy";
    });
    lista.appendChild(el);
  }
}

function renderPrograma(resaltado = null, error = false) {
  const lista = $("#programa");
  lista.innerHTML = "";
  app.programa.forEach((clave, i) => {
    const el = crearBloque(clave, i);
    if (resaltado === i) el.classList.add(error ? "error" : "actual");
    el.querySelector(".borrar").addEventListener("click", (e) => { e.stopPropagation(); borrarBloque(i); });
    el.addEventListener("dragstart", (e) => {
      if (app.ejecutando) { e.preventDefault(); return; }
      e.dataTransfer.setData("text/plain", JSON.stringify({ origen: "programa", indice: i }));
      e.dataTransfer.effectAllowed = "move";
      requestAnimationFrame(() => el.classList.add("arrastrando"));
    });
    el.addEventListener("dragend", () => el.classList.remove("arrastrando"));
    lista.appendChild(el);
  });
  $("#programa-vacio").hidden = app.programa.length > 0;
  if (resaltado !== null) lista.children[resaltado]?.scrollIntoView({ block: "nearest" });
}

function indiceInsercion(y) {
  const items = [...$("#programa").querySelectorAll(".blk")];
  for (let i = 0; i < items.length; i++) {
    const r = items[i].getBoundingClientRect();
    if (y < r.top + r.height / 2) return i;
  }
  return items.length;
}

function mostrarMarcador(indice) {
  quitarMarcador();
  const lista = $("#programa");
  const m = document.createElement("li");
  m.className = "marcador";
  const items = lista.querySelectorAll(".blk");
  lista.insertBefore(m, items[indice] || null);
}
function quitarMarcador() { document.querySelectorAll(".marcador").forEach((m) => m.remove()); }

function agregarBloque(clave, indice) {
  if (app.ejecutando) return;
  if (app.vista === "python") {
    const t = $("#codigo").value.replace(/\n+$/, "");
    ponerCodigo((t ? t + "\n" : "") + BLOQUES[clave].linea);
    return;
  }
  if (indice === undefined) app.programa.push(clave);
  else app.programa.splice(indice, 0, clave);
  programaCambiado();
}

function borrarBloque(i) {
  if (app.ejecutando) return;
  app.programa.splice(i, 1);
  programaCambiado();
}

function programaCambiado() {
  app.lineaABloque = Object.fromEntries(app.programa.map((_, i) => [i + 1, i]));
  renderPrograma();
  ponerCodigo(codigoDeBloques());
}

function codigoDeBloques() { return app.programa.map((k) => BLOQUES[k].linea).join("\n"); }

// ---------------------------------------------------------------------------
// Editor de Python (textarea transparente sobre un fondo coloreado)
// ---------------------------------------------------------------------------
function escapar(t) { return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function pintarEditor(lineaMarcada = null, tipo = "actual") {
  const lineas = $("#codigo").value.split("\n");
  $("#resaltado").innerHTML = lineas.map((l, i) => {
    let h = escapar(l)
      .replace(/"[^"]*"/g, (m) => `<span class="str">${m}</span>`)
      .replace(/\b(mover|recoger|entregar)\b/g, '<span class="fn">$1</span>');
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
    const r = llamarPy("preparar", $("#codigo").value);
    llamarPy("reiniciar");
    if (!r.ok) {
      aviso(`No se puede pasar a bloques — línea ${r.linea}: ${r.motivo}`);
      pintarEditor(r.linea, "error");
      return false;
    }
    app.programa = r.instr.map((i) => (i.nombre === "mover" ? i.args[0] : i.nombre));
    app.lineaABloque = Object.fromEntries(r.instr.map((i, n) => [i.linea, n]));
  } else {
    ponerCodigo(codigoDeBloques());
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

function codigoActual() { return app.vista === "bloques" ? codigoDeBloques() : $("#codigo").value; }

function resaltar(linea, error = false) {
  if (app.vista === "bloques") {
    const i = linea == null ? null : app.lineaABloque[linea];
    renderPrograma(i ?? null, error);
  } else {
    pintarEditor(linea, error ? "error" : "actual");
  }
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

  // entrega
  let [x, y] = centro(inf.entrega);
  svg("rect", { x: x - 27, y: y - 27, width: 54, height: 54, rx: 9, fill: "#0f2f22",
                stroke: estado.modulo === "entregado" ? "#22c55e" : "#15803d", "stroke-width": 2, "stroke-dasharray": "5 3" }, m);
  svg("text", { x, y: y - 16, fill: "#86efac", "font-size": 8, "font-weight": 800, "text-anchor": "middle" }, m).textContent = "ENTREGA";

  // obstáculos (asteroides)
  for (const p of inf.obstaculos) {
    [x, y] = centro(p);
    const g = svg("g", { transform: `translate(${x} ${y})` }, m);
    svg("path", { d: "M-22 6 Q-20 -16 -4 -21 Q16 -22 21 -6 Q25 12 6 21 Q-14 25 -22 6Z", fill: "#4b5068", stroke: "#71779a", "stroke-width": 2 }, g);
    svg("circle", { cx: -7, cy: -5, r: 4, fill: "#3a3e52" }, g);
    svg("circle", { cx: 9, cy: 8, r: 5, fill: "#3a3e52" }, g);
  }

  // rastro
  if (app.rastro.length > 1)
    svg("polyline", { points: app.rastro.map((p) => centro(p).join(",")).join(" "), fill: "none",
                      stroke: "#5b8cff", "stroke-width": 3, "stroke-dasharray": "6 5", "stroke-linecap": "round" }, m);

  // módulo
  if (estado.modulo === "disponible") {
    [x, y] = centro(inf.modulo);
    dibujarModulo(m, x, y - 2, 0.85);
    svg("text", { x, y: y + 22, fill: "#fcd34d", "font-size": 8, "font-weight": 800, "text-anchor": "middle" }, m).textContent = "MÓDULO";
  } else if (estado.modulo === "entregado") {
    [x, y] = centro(inf.entrega);
    dibujarModulo(m, x, y + 6, 0.65);
  }

  // marca de error
  if (errorEn && dentro(errorEn)) {
    [x, y] = centro(errorEn);
    svg("circle", { cx: x, cy: y, r: 27, fill: "none", stroke: "#ef4444", "stroke-width": 4 }, m);
  }

  // robot
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
  // anima el robot existente; luego se redibuja todo el mapa
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
  for (const id of ["#btn-ejecutar", "#btn-reiniciar", "#btn-borrar", "#tab-bloques", "#tab-python", "#caso"])
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
  const codigo = codigoActual();
  reiniciar();
  if (app.vista === "bloques") app.lineaABloque = Object.fromEntries(app.programa.map((_, i) => [i + 1, i]));
  const r = llamarPy("preparar", codigo);
  if (!r.ok) {
    registrar(`Código rechazado — línea ${r.linea}: ${r.motivo}`, "error");
    registrar("No se ejecutó ninguna acción.", "error");
    resaltar(r.linea, true);
    mostrarResultado("detenida", r.mensaje);
    return;
  }
  if (app.vista === "python") app.lineaABloque = Object.fromEntries(r.instr.map((i, n) => [i.linea, n]));
  registrar(`Código válido: ${r.instr.length} instrucciones.`, "ok");
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
    registrar(`L${i.linea}  ${i.texto}  ✗ ${r.motivo}`, "error");
    resaltar(i.linea, true);
    let destino = r.estado.pos;
    if (i.nombre === "mover") {
      const d = { norte: [-1, 0], sur: [1, 0], oeste: [0, -1], este: [0, 1] }[i.args[0]];
      destino = [r.estado.pos[0] + d[0], r.estado.pos[1] + d[1]];
    }
    dibujarMapa(r.estado, destino);
    return terminar("detenida", r.mensaje, false);
  }
  registrar(`L${i.linea}  ${r.detalle}`, i.nombre === "mover" ? "" : "ok");
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
  $("#btn-borrar").addEventListener("click", () => { reiniciar(); app.programa = []; programaCambiado(); });
  $("#caso").addEventListener("change", cargarCaso);

  const ta = $("#codigo");
  ta.addEventListener("input", () => pintarEditor());
  ta.addEventListener("scroll", sincronizarScroll);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const p = ta.selectionStart;
      ta.setRangeText("    ", p, ta.selectionEnd, "end");
      pintarEditor();
    }
  });

  // arrastrar y soltar en el programa
  const zona = $("#vista-bloques");
  zona.addEventListener("dragover", (e) => {
    e.preventDefault();
    mostrarMarcador(indiceInsercion(e.clientY));
  });
  zona.addEventListener("dragleave", (e) => { if (!zona.contains(e.relatedTarget)) quitarMarcador(); });
  zona.addEventListener("drop", (e) => {
    e.preventDefault();
    quitarMarcador();
    let datos;
    try { datos = JSON.parse(e.dataTransfer.getData("text/plain")); } catch { return; }
    const destino = indiceInsercion(e.clientY);
    if (datos.origen === "paleta") return agregarBloque(datos.clave, destino);
    const [clave] = app.programa.splice(datos.indice, 1);
    app.programa.splice(destino > datos.indice ? destino - 1 : destino, 0, clave);
    programaCambiado();
  });
  // soltar un bloque del programa fuera de la zona = borrarlo
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => {
    if (zona.contains(e.target)) return;
    e.preventDefault();
    quitarMarcador();
    try {
      const datos = JSON.parse(e.dataTransfer.getData("text/plain"));
      if (datos.origen === "programa") borrarBloque(datos.indice);
    } catch { /* no era un bloque */ }
  });
}

iniciar();

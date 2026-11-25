// Componentes DOM pequeños, formatos compartidos, estados y notificaciones.
export function h(etiqueta, propiedades = {}, ...hijos) {
  const elemento = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(propiedades)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (clave === "className") {
      elemento.className = valor;
    } else if (clave.startsWith("on")) {
      elemento.addEventListener(clave.slice(2), valor);
    } else if (clave === "dataset") {
      Object.assign(elemento.dataset, valor);
    } else if (typeof valor === "boolean") {
      elemento[clave] = valor;
    } else if (clave === "value") {
      elemento.value = valor;
    } else {
      elemento.setAttribute(clave, valor);
    }
  }
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    elemento.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return elemento;
}

export function toast(mensaje, tipo = "info") {
  const contenedor = document.getElementById("toasts");
  const aviso = h("div", { className: `toast ${tipo}` }, mensaje);
  contenedor.append(aviso);
  while (contenedor.children.length > 4) {
    contenedor.firstElementChild.remove();
  }
  setTimeout(() => aviso.remove(), tipo === "error" ? 7000 : 4000);
}

export function errorVisible(error) {
  const bloque = h("div", { className: "error" }, error.message);
  if (error.status === 401) {
    bloque.append(" ", h("a", { href: "#/ajustes" }, "Revisa la clave en Ajustes."));
  }
  return bloque;
}

export function vacio(texto) {
  return h("p", { className: "vacio" }, texto);
}

export function formatearFecha(iso) {
  if (!iso) return "—";
  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (soloFecha) return `${soloFecha[3]}/${soloFecha[2]}/${soloFecha[1]}`;
  return iso;
}

export function formatearFechaHora(iso) {
  if (!iso) return "—";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return iso;
  return fecha.toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatearMinuto(segundos) {
  const total = Math.floor(Number(segundos) || 0);
  const horas = Math.floor(total / 3600);
  const minutos = Math.floor((total % 3600) / 60);
  const resto = total % 60;
  const dos = (n) => String(n).padStart(2, "0");
  return horas ? `${horas}:${dos(minutos)}:${dos(resto)}` : `${dos(minutos)}:${dos(resto)}`;
}

const ETIQUETAS_ESTADO = {
  abierto: "Abierto",
  resuelto: "Resuelto",
  pospuesto: "Pospuesto",
};

const ETIQUETAS_ALERTA = {
  recurrente: "Recurrente",
  antiguo: "Antiguo",
};

export function badgeEstado(estado) {
  return h("span", { className: `badge estado-${estado}` }, ETIQUETAS_ESTADO[estado] || estado);
}

export function badgesAlerta(alertas = []) {
  return alertas.map((alerta) =>
    h("span", { className: `badge alerta-${alerta}` }, ETIQUETAS_ALERTA[alerta] || alerta)
  );
}

export function cargando(texto = "Cargando…") {
  return h("p", { className: "cargando" }, texto);
}

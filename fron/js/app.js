// Enrutador y puerta de sesión de la aplicación.
import { api, cerrarSesion, obtenerToken } from "./api.js";
import { h, errorVisible, cargando, toast } from "./ui.js";
import { mostrarAcceso } from "./vistas/acceso.js";
import { abrirPerfil } from "./vistas/perfil.js";
import { mostrarListado, mostrarDetalle } from "./vistas/reuniones.js";
import { mostrarPreguntas } from "./vistas/preguntas.js";
import { mostrarTemas, mostrarTema } from "./vistas/temas.js";
import { mostrarVocabulario } from "./vistas/vocabulario.js";
import { mostrarAjustes } from "./vistas/ajustes.js";

const acceso = document.getElementById("acceso");
const shell = document.getElementById("app-shell");
const saltoContenido = document.querySelector(".salto-contenido");
const contenido = document.getElementById("vista");
const emailPerfil = document.getElementById("perfil-email");
const avatarPerfil = document.getElementById("perfil-avatar");

const rutas = {
  reuniones: (id, params) =>
    id ? mostrarDetalle(contenido, id, params) : mostrarListado(contenido),
  preguntas: () => mostrarPreguntas(contenido),
  temas: (id) => (id ? mostrarTema(contenido, id) : mostrarTemas(contenido)),
  vocabulario: () => mostrarVocabulario(contenido),
  ajustes: () => mostrarAjustes(contenido),
};

function leerHash() {
  const [ruta, consulta = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const partes = ruta.split("/").filter(Boolean);
  return {
    seccion: partes[0] || "reuniones",
    id: partes[1],
    params: new URLSearchParams(consulta),
  };
}

function mostrarShell(usuario) {
  acceso.replaceChildren();
  shell.hidden = false;
  saltoContenido.hidden = false;
  emailPerfil.textContent = usuario?.email || "Cuenta";
  if (usuario?.avatar_url) {
    avatarPerfil.replaceChildren(h("img", { src: usuario.avatar_url, alt: "" }));
  } else {
    avatarPerfil.textContent = (usuario?.email?.[0] || "U").toLocaleUpperCase("es-ES");
  }
}

function mostrarPantallaAcceso() {
  document.getElementById("dialog-perfil")?.close();
  shell.hidden = true;
  saltoContenido.hidden = true;
  mostrarAcceso(acceso, async (usuario) => {
    mostrarShell(usuario);
    if (!location.hash) history.replaceState(null, "", "#/reuniones");
    await navegar(true);
  });
}

async function navegar(enfocar = false) {
  if (!obtenerToken() || shell.hidden) return;
  const { seccion, id, params } = leerHash();
  document.querySelectorAll(".lateral nav a").forEach((enlace) => {
    const activo = enlace.dataset.seccion === seccion;
    enlace.classList.toggle("activo", activo);
    if (activo) enlace.setAttribute("aria-current", "page");
    else enlace.removeAttribute("aria-current");
  });

  const vista = rutas[seccion] || rutas.reuniones;
  contenido.replaceChildren(cargando());
  try {
    await vista(id, params);
  } catch (error) {
    contenido.replaceChildren(errorVisible(error));
  }
  if (enfocar) contenido.focus({ preventScroll: true });
}

async function iniciarAplicacion() {
  if (!obtenerToken()) {
    mostrarPantallaAcceso();
    return;
  }
  try {
    const usuario = await api("/auth/me");
    mostrarShell(usuario);
    if (!location.hash) history.replaceState(null, "", "#/reuniones");
    await navegar(true);
  } catch (error) {
    if (error.status === 401) {
      cerrarSesion();
      mostrarPantallaAcceso();
      return;
    }
    mostrarShell(null);
    contenido.replaceChildren(errorVisible(error));
  }
}

function salirDeLaCuenta() {
  cerrarSesion();
  location.hash = "";
  mostrarPantallaAcceso();
}

document.getElementById("abrir-perfil").addEventListener("click", async () => {
  try {
    await abrirPerfil(mostrarShell, salirDeLaCuenta);
  } catch (error) {
    toast(error.message, "error");
  }
});

document.getElementById("cerrar-sesion").addEventListener("click", salirDeLaCuenta);

window.addEventListener("hashchange", () => navegar(true));
window.addEventListener("recargar", () => navegar());
window.addEventListener("sesion-caducada", mostrarPantallaAcceso);
iniciarAplicacion();

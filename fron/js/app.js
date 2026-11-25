// Enrutador de la aplicación: interpreta el hash y carga cada vista.
import { h, errorVisible, cargando } from "./ui.js";
import { mostrarListado, mostrarDetalle } from "./vistas/reuniones.js";
import { mostrarPreguntas } from "./vistas/preguntas.js";
import { mostrarTemas, mostrarTema } from "./vistas/temas.js";
import { mostrarVocabulario } from "./vistas/vocabulario.js";
import { mostrarAjustes } from "./vistas/ajustes.js";

const contenido = document.getElementById("contenido");

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

async function navegar() {
  const { seccion, id, params } = leerHash();
  document
    .querySelectorAll(".lateral nav a")
    .forEach((enlace) => enlace.classList.toggle("activo", enlace.dataset.seccion === seccion));

  const vista = rutas[seccion] || rutas.reuniones;
  contenido.replaceChildren(cargando());
  try {
    await vista(id, params);
  } catch (error) {
    contenido.replaceChildren(errorVisible(error));
  }
}

window.addEventListener("hashchange", navegar);
window.addEventListener("recargar", navegar);
navegar();

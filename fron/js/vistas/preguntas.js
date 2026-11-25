// Chat RAG: preguntas, fuentes citadas y enlaces al minuto de la transcripción.
import { api } from "../api.js";
import { h, toast, formatearFecha, formatearMinuto, vacio, cargando } from "../ui.js";

let conversacion = [];
let seleccionadas = new Set();
let contadorMensajes = 0;

function fragmentoDeRespuesta(texto, idMensaje) {
  return texto.split(/(\[\d+\])/).map((parte) => {
    const coincidencia = /^\[(\d+)\]$/.exec(parte);
    if (!coincidencia) return parte;
    const numero = coincidencia[1];
    return h(
      "button",
      {
        className: "cita",
        type: "button",
        onclick: () =>
          document
            .getElementById(`fuente-${idMensaje}-${numero}`)
            ?.scrollIntoView({ block: "center" }),
      },
      parte
    );
  });
}

function tarjetaFuente(fuente, idMensaje) {
  return h(
    "article",
    { className: "fuente", id: `fuente-${idMensaje}-${fuente.referencia}` },
    h(
      "div",
      { className: "fuente-cabecera" },
      h("span", { className: "badge" }, `[${fuente.referencia}]`),
      h(
        "strong",
        {},
        `Reunión #${fuente.reunion_id}`
      ),
      h("span", { className: "ayuda" }, ` · ${formatearFecha(fuente.reunion_fecha)} · min ${formatearMinuto(fuente.inicio_segundos)} · Hablante ${fuente.hablante}`)
    ),
    h("p", { className: "fuente-texto" }, fuente.texto),
    h(
      "a",
      {
        className: "enlace-fuente",
        href: `#/reuniones/${fuente.reunion_id}?tab=transcripcion&min=${fuente.inicio_segundos}`,
      },
      "Abrir la reunión en este minuto"
    )
  );
}

function burbujaRespuesta(mensaje, idMensaje) {
  const parrafos = mensaje.respuesta.split("\n").filter((linea) => linea.trim());
  return h(
    "div",
    { className: "mensaje respuesta" },
    parrafos.map((linea) => h("p", {}, fragmentoDeRespuesta(linea, idMensaje))),
    mensaje.fuentes.length
      ? h("div", { className: "fuentes" }, h("h4", {}, "Fuentes"), mensaje.fuentes.map((fuente) => tarjetaFuente(fuente, idMensaje)))
      : null
  );
}

export async function mostrarPreguntas(contenedor) {
  const reuniones = await api("/reuniones");
  const areaMensajes = h("div", { className: "conversacion" });

  function pintarConversacion() {
    if (!conversacion.length) {
      areaMensajes.replaceChildren(
        vacio("Pregunta algo como “¿qué acordamos con el cliente sobre el presupuesto?”. Las respuestas citan la reunión y el minuto.")
      );
      return;
    }
    areaMensajes.replaceChildren(
      ...conversacion.map((mensaje) =>
        mensaje.tipo === "pregunta"
          ? h("div", { className: "mensaje pregunta" }, mensaje.texto)
          : burbujaRespuesta(mensaje, mensaje.id)
      )
    );
    areaMensajes.scrollTop = areaMensajes.scrollHeight;
  }

  const entrada = h("textarea", {
    rows: 2,
    "aria-label": "Escribe una pregunta sobre tus reuniones",
    placeholder: "Escribe tu pregunta…",
    required: true,
    onkeydown: (evento) => {
      if (evento.key === "Enter" && !evento.shiftKey) {
        evento.preventDefault();
        evento.currentTarget.form.requestSubmit();
      }
    },
  });
  const enviar = h("button", { type: "submit", className: "boton" }, "Preguntar");

  const formulario = h(
    "form",
    {
      className: "entrada-pregunta",
      onsubmit: async (evento) => {
        evento.preventDefault();
        const pregunta = entrada.value.trim();
        if (pregunta.length < 3) {
          toast("Escribe una pregunta un poco más larga", "error");
          return;
        }

        conversacion.push({ tipo: "pregunta", texto: pregunta });
        entrada.value = "";
        enviar.disabled = true;
        areaMensajes.append(cargando("Buscando en tus reuniones…"));

        try {
          const respuesta = await api("/preguntas", {
            metodo: "POST",
            cuerpo: {
              pregunta,
              reuniones: seleccionadas.size ? [...seleccionadas] : null,
              limite: 8,
            },
          });
          contadorMensajes += 1;
          conversacion.push({ tipo: "respuesta", id: contadorMensajes, ...respuesta });
        } catch (error) {
          conversacion.push({ tipo: "respuesta", id: 0, respuesta: error.message, fuentes: [] });
          toast(error.message, "error");
        } finally {
          enviar.disabled = false;
          pintarConversacion();
        }
      },
    },
    entrada,
    enviar
  );

  const textoSeleccion = h("p", { className: "ayuda" });
  function pintarSeleccion() {
    textoSeleccion.textContent = seleccionadas.size
      ? `${seleccionadas.size} reunión(es) seleccionadas`
      : "Todas las reuniones";
  }
  pintarSeleccion();

  const listaReuniones = h(
    "div",
    { className: "filtro-reuniones", "aria-labelledby": "filtro-reuniones-titulo" },
    reuniones.length === 0
      ? vacio("No hay reuniones guardadas todavía.")
      : reuniones.map((reunion) =>
          h(
            "label",
            { className: "casilla" },
            h("input", {
              type: "checkbox",
              checked: seleccionadas.has(reunion.id),
              onchange: (evento) => {
                if (evento.currentTarget.checked) seleccionadas.add(reunion.id);
                else seleccionadas.delete(reunion.id);
                pintarSeleccion();
              },
            }),
            ` #${reunion.id} · ${formatearFecha(reunion.created_at)}`
          )
        )
  );

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h("h1", {}, "Preguntar a tus reuniones"),
      h(
        "button",
        {
          className: "boton secundario",
          onclick: () => {
            conversacion = [];
            pintarConversacion();
          },
        },
        "Nueva conversación"
      )
    ),
    h(
      "div",
      { className: "preguntas-layout" },
      h(
        "aside",
        { className: "panel" },
        h("h3", { id: "filtro-reuniones-titulo" }, "Buscar en"),
        textoSeleccion,
        listaReuniones
      ),
      h("section", { className: "chat" }, areaMensajes, formulario)
    )
  );

  pintarConversacion();
}

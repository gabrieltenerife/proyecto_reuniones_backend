// Listado y detalle de reuniones: transcripción, resumen, temas, exportación e historial.
import { api } from "../api.js";
import {
  h,
  toast,
  formatearFecha,
  formatearFechaHora,
  formatearMinuto,
  badgeEstado,
  badgesAlerta,
  cargando,
  vacio,
} from "../ui.js";

const PESTANAS = [
  ["transcripcion", "Transcripción"],
  ["resumen", "Resumen"],
  ["temas", "Temas"],
  ["exportar", "Exportar"],
  ["versiones", "Versiones"],
];

const ETIQUETAS_ORIGEN = {
  edicion_segmento: "Edición de un segmento",
  correccion_global: "Corrección en toda la reunión",
  edicion_manual: "Edición manual del resumen",
  antes_de_regenerar: "Antes de regenerar el resumen",
  antes_de_restaurar: "Antes de restaurar",
};

const ETIQUETAS_CAMPO = {
  transcripcion: "Transcripción",
  texto_resumido: "Resumen",
};

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

let tiposCache = null;

async function obtenerTipos() {
  if (!tiposCache) {
    tiposCache = await api("/tipos");
  }
  return tiposCache;
}

function nombreTipo(tipos, id) {
  return tipos.find((tipo) => tipo.id === id)?.nombre || id;
}

function recargar() {
  window.dispatchEvent(new Event("recargar"));
}

export async function mostrarListado(contenedor) {
  const [reuniones, tipos] = await Promise.all([api("/reuniones"), obtenerTipos()]);

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h("h1", {}, "Reuniones"),
      h("span", { className: "subtitulo" }, `${reuniones.length} reuniones en tu espacio`),
      h("a", { className: "boton secundario", href: "#/preguntas" }, "Preguntar a tus reuniones")
    ),
    reuniones.length === 0
      ? vacio("Todavía no hay reuniones. Ejecuta main.py para procesar un audio.")
      : h(
          "div",
          { className: "tabla-contenedor" },
          h(
            "table",
            { className: "tabla" },
            h("caption", { className: "solo-lectores" }, "Reuniones guardadas en tu espacio"),
            h(
              "thead",
              {},
              h("tr", {},
                h("th", { scope: "col" }, "Reunión"),
                h("th", { scope: "col" }, "Fecha"),
                h("th", { scope: "col" }, "Tipo"),
                h("th", { scope: "col" }, "Acciones")
              )
            ),
            h(
              "tbody",
              {},
              reuniones.map((reunion) =>
                h(
                  "tr",
                  {},
                  h("td", {}, `#${reunion.id}`),
                  h("td", {}, formatearFecha(reunion.created_at)),
                  h("td", {}, nombreTipo(tipos, reunion.tipo)),
                  h(
                    "td",
                    { className: "derecha" },
                    h("a", {
                      className: "boton secundario pequeno",
                      href: `#/reuniones/${reunion.id}`,
                      "aria-label": `Abrir reunión ${reunion.id}`,
                    }, "Abrir")
                  )
                )
              )
            )
          )
        )
  );
}

export async function mostrarDetalle(contenedor, id, params) {
  const [reunion, tipos] = await Promise.all([api(`/reuniones/${id}`), obtenerTipos()]);
  const pestanaSolicitada = params.get("tab") || "transcripcion";
  let pestanaActiva = Math.max(0, PESTANAS.findIndex(([clave]) => clave === pestanaSolicitada));
  const minutoParam = params.get("min");
  const minuto = minutoParam === null ? null : Number(minutoParam);

  const cargarPanel = {
    transcripcion: () => panelTranscripcion(id, reunion, minuto),
    resumen: () => panelResumen(id, reunion, tipos),
    temas: () => panelTemas(id),
    exportar: () => panelExportar(id),
    versiones: () => panelVersiones(id),
  };

  const indexar = h(
    "button",
    {
      className: "boton secundario",
      onclick: async (evento) => {
        const boton = evento.currentTarget;
        boton.disabled = true;
        try {
          const resultado = await api(`/reuniones/${id}/indexar`, { metodo: "POST" });
          toast(`Reunión indexada: ${resultado.fragmentos} fragmentos`, "ok");
        } catch (error) {
          toast(error.message, "error");
        } finally {
          boton.disabled = false;
        }
      },
    },
    "Reindexar búsqueda"
  );

  const indicadorPestana = h("span", {
    className: "indicador-pestana",
    "aria-hidden": "true",
  });
  const pestanas = h(
    "nav",
    { className: "pestanas", role: "tablist", "aria-label": "Secciones de la reunión" },
    PESTANAS.map(([clave, texto], indice) =>
      h(
        "button",
        {
          id: `pestana-${clave}`,
          type: "button",
          role: "tab",
          className: indice === pestanaActiva ? "activa" : "",
          "aria-selected": indice === pestanaActiva ? "true" : "false",
          "aria-controls": `panel-${clave}`,
          tabindex: indice === pestanaActiva ? 0 : -1,
          onclick: () => seleccionar(indice, true),
          onkeydown: (evento) => {
            let siguiente = null;
            if (evento.key === "ArrowRight") siguiente = (indice + 1) % PESTANAS.length;
            if (evento.key === "ArrowLeft") siguiente = (indice - 1 + PESTANAS.length) % PESTANAS.length;
            if (evento.key === "Home") siguiente = 0;
            if (evento.key === "End") siguiente = PESTANAS.length - 1;
            if (siguiente !== null) {
              evento.preventDefault();
              seleccionar(siguiente, true);
            }
          },
        },
        texto
      )
    ),
    indicadorPestana
  );

  const slides = PESTANAS.map(([clave], indice) =>
    h(
      "section",
      {
        id: `panel-${clave}`,
        className: "panel-slide",
        role: "tabpanel",
        "aria-labelledby": `pestana-${clave}`,
        "aria-hidden": indice === pestanaActiva ? "false" : "true",
        tabindex: 0,
      },
      indice === pestanaActiva ? cargando() : null
    )
  );
  const track = h("div", { className: "panel-track" }, slides);
  track.style.transform = `translate3d(${pestanaActiva * 100}%, 0, 0)`;
  const viewport = h("div", { className: "panel-viewport" }, track);
  const cargados = new Set();
  const cargandoPaneles = new Set();

  function posicionarIndicador() {
    const boton = pestanas.querySelectorAll('[role="tab"]')[pestanaActiva];
    indicadorPestana.style.width = `${boton.offsetWidth}px`;
    indicadorPestana.style.transform = `translateX(${boton.offsetLeft}px)`;
  }

  function ajustarAltura(indice) {
    viewport.style.height = `${slides[indice].scrollHeight}px`;
  }

  async function cargar(indice) {
    if (cargados.has(indice) || cargandoPaneles.has(indice)) return;
    cargandoPaneles.add(indice);
    const [clave] = PESTANAS[indice];
    const slide = slides[indice];
    slide.replaceChildren(cargando(`Cargando ${PESTANAS[indice][1].toLowerCase()}…`));
    try {
      slide.replaceChildren(await cargarPanel[clave]());
      cargados.add(indice);
      if (indice === pestanaActiva) requestAnimationFrame(() => ajustarAltura(indice));
      if (clave === "transcripcion" && minuto !== null) {
        slide.querySelector(".resaltado")?.scrollIntoView({ block: "center" });
      }
    } catch (error) {
      slide.replaceChildren(
        h("div", { className: "error", role: "alert" }, error.message),
        h(
          "button",
          {
            type: "button",
            className: "boton secundario",
            onclick: () => cargar(indice),
          },
          "Volver a intentar"
        )
      );
    } finally {
      cargandoPaneles.delete(indice);
    }
  }

  function actualizarDireccion(clave) {
    const consulta = new URLSearchParams({ tab: clave });
    if (clave === "transcripcion" && params.has("min")) {
      consulta.set("min", params.get("min"));
    }
    history.replaceState(null, "", `#/reuniones/${id}?${consulta}`);
  }

  function seleccionar(indice, enfocar = false) {
    pestanaActiva = indice;
    const claveActiva = PESTANAS[indice][0];
    pestanas.querySelectorAll('[role="tab"]').forEach((boton, posicion) => {
      const activa = posicion === indice;
      boton.classList.toggle("activa", activa);
      boton.setAttribute("aria-selected", String(activa));
      boton.tabIndex = activa ? 0 : -1;
    });
    slides.forEach((slide, posicion) => {
      const activa = posicion === indice;
      slide.setAttribute("aria-hidden", String(!activa));
      slide.inert = !activa;
    });
    track.style.transform = `translate3d(${indice * 100}%, 0, 0)`;
    actualizarDireccion(claveActiva);
    if (enfocar) pestanas.querySelectorAll('[role="tab"]')[indice].focus();
    requestAnimationFrame(posicionarIndicador);
    requestAnimationFrame(() => ajustarAltura(indice));
    void cargar(indice);
  }

  function deslizarPorGesto(evento) {
    if (Math.abs(evento.changedTouches[0].clientX - inicioToque.x) < 55) return;
    if (Math.abs(evento.changedTouches[0].clientY - inicioToque.y) > 70) return;
    const direccion = evento.changedTouches[0].clientX < inicioToque.x ? 1 : -1;
    const siguiente = pestanaActiva + direccion;
    if (siguiente >= 0 && siguiente < PESTANAS.length) seleccionar(siguiente);
  }

  const inicioToque = { x: 0, y: 0 };
  viewport.addEventListener("touchstart", (evento) => {
    inicioToque.x = evento.changedTouches[0].clientX;
    inicioToque.y = evento.changedTouches[0].clientY;
  }, { passive: true });
  viewport.addEventListener("touchend", deslizarPorGesto, { passive: true });

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h(
        "div",
        {},
        h("a", { className: "migaja", href: "#/reuniones" }, "← Reuniones"),
        h("h1", {}, `Reunión #${id}`),
        h(
          "span",
          { className: "subtitulo" },
          `${formatearFechaHora(reunion.created_at)} · ${nombreTipo(tipos, reunion.tipo)}`
        )
      ),
      h("div", { className: "acciones" }, indexar)
    ),
    pestanas,
    viewport
  );

  slides.forEach((slide, indice) => { slide.inert = indice !== pestanaActiva; });
  requestAnimationFrame(posicionarIndicador);
  if ("ResizeObserver" in window) {
    const observadorTamano = new ResizeObserver(() => {
      if (!pestanas.isConnected) {
        observadorTamano.disconnect();
        return;
      }
      posicionarIndicador();
    });
    observadorTamano.observe(pestanas);
  }
  void cargar(pestanaActiva);
  requestAnimationFrame(() => ajustarAltura(pestanaActiva));
}

function indiceDeMinuto(segmentos, minuto) {
  const dentro = segmentos.findIndex((segmento) => minuto >= segmento.start && minuto <= segmento.end);
  if (dentro >= 0) return dentro;

  let mejor = -1;
  let distancia = Infinity;
  segmentos.forEach((segmento, indice) => {
    const diferencia = Math.abs(segmento.start - minuto);
    if (diferencia < distancia) {
      distancia = diferencia;
      mejor = indice;
    }
  });
  return mejor;
}

function panelTranscripcion(id, reunion, minuto) {
  const segmentos = reunion.transcripcion?.segments || [];
  const indiceResaltado = minuto === null || !segmentos.length ? -1 : indiceDeMinuto(segmentos, minuto);

  const buscar = h("input", {
    "aria-label": "Texto que se va a corregir",
    placeholder: "Texto a corregir, p. ej. cuberneti",
    required: true,
  });
  const reemplazar = h("input", {
    "aria-label": "Texto correcto que lo sustituirá",
    placeholder: "Corregir a, p. ej. Kubernetes",
    required: true,
  });
  const recordar = h("input", { type: "checkbox", checked: true });

  const correccion = h(
    "form",
    {
      className: "panel correccion",
      onsubmit: async (evento) => {
        evento.preventDefault();
        try {
          const resultado = await api(`/reuniones/${id}/correcciones`, {
            metodo: "POST",
            cuerpo: {
              buscar: buscar.value.trim(),
              reemplazar: reemplazar.value.trim(),
              recordar: recordar.checked,
            },
          });
          const guardado = resultado.recordado ? " y guardado en el vocabulario" : "";
          toast(`${resultado.reemplazos} cambio(s) aplicados${guardado}`, "ok");
          recargar();
        } catch (error) {
          toast(error.message, "error");
        }
      },
    },
    h("h3", {}, "Corregir en toda la reunión"),
    h("div", { className: "fila" }, buscar, h("span", { className: "flecha" }, "→"), reemplazar),
    h("label", { className: "casilla" }, recordar, " Recordar en el vocabulario"),
    h("div", { className: "acciones" }, h("button", { type: "submit", className: "boton" }, "Aplicar a toda la reunión"))
  );

  if (!segmentos.length) {
    return h("section", {}, correccion, vacio("Esta reunión no tiene transcripción."));
  }

  return h(
    "section",
    {},
    correccion,
    h(
      "div",
      { className: "segmentos" },
      segmentos.map((segmento, indice) => filaSegmento(id, segmento, indice, indice === indiceResaltado))
    )
  );
}

function bloqueSugerencias(sugerencias) {
  if (!sugerencias || !sugerencias.length) return null;
  return h(
    "div",
    { className: "sugerencias" },
    h("p", { className: "ayuda" }, "Parece una corrección de vocabulario:"),
    sugerencias.map((sugerencia) => {
      const boton = h(
        "button",
        {
          className: "boton secundario pequeno",
          onclick: async () => {
            try {
              await api("/vocabulario", {
                metodo: "POST",
                cuerpo: { termino: sugerencia.termino, variante: sugerencia.variante },
              });
              boton.textContent = "Guardado";
              boton.disabled = true;
            } catch (error) {
              toast(error.message, "error");
            }
          },
        },
        "Recordar"
      );
      return h("div", { className: "sugerencia" }, `${sugerencia.variante} → ${sugerencia.termino} `, boton);
    })
  );
}

function filaSegmento(id, segmento, indice, resaltado) {
  const fila = h("article", {
    className: `segmento${resaltado ? " resaltado" : ""}`,
    id: `seg-${indice}`,
  });

  function cabecera(conEditar) {
    return h(
      "div",
      { className: "segmento-cabecera" },
      h("span", { className: "minuto" }, formatearMinuto(segmento.start)),
      h("span", { className: "hablante" }, `Hablante ${segmento.speaker}`),
      conEditar ? h("button", { className: "enlace", onclick: () => editar() }, "Editar") : null
    );
  }

  function verTexto(sugerencias = []) {
    const bloque = bloqueSugerencias(sugerencias);
    fila.replaceChildren(cabecera(true), h("p", { className: "texto" }, segmento.text), ...(bloque ? [bloque] : []));
  }

  function editar() {
    const area = h("textarea", {
      rows: 3,
      value: segmento.text,
      "aria-label": `Texto del segmento ${indice + 1}, hablante ${segmento.speaker}`,
    });
    const guardar = h(
      "button",
      {
        className: "boton",
        onclick: async (evento) => {
          const boton = evento.currentTarget;
          boton.disabled = true;
          try {
            const resultado = await api(`/reuniones/${id}/segmentos/${indice}`, {
              metodo: "PATCH",
              cuerpo: { texto: area.value },
            });
            segmento.text = resultado.segmento.text;
            verTexto(resultado.sugerencias_vocabulario);
            toast("Segmento guardado", "ok");
          } catch (error) {
            toast(error.message, "error");
            boton.disabled = false;
          }
        },
      },
      "Guardar"
    );
    const cancelar = h("button", { className: "boton secundario", onclick: () => verTexto() }, "Cancelar");

    fila.replaceChildren(cabecera(false), area, h("div", { className: "acciones" }, cancelar, guardar));
    area.focus();
  }

  verTexto();
  return fila;
}

function panelResumen(id, reunion, tipos) {
  const selectTipo = h(
    "select",
    { "aria-label": "Tipo de reunión para el resumen" },
    tipos.map((tipo) => h("option", { value: tipo.id }, tipo.nombre))
  );
  selectTipo.value = reunion.tipo;

  const secciones = h("ul", { className: "secciones" });
  function pintarSecciones() {
    const tipo = tipos.find((item) => item.id === selectTipo.value);
    secciones.replaceChildren(...(tipo?.secciones || []).map((seccion) => h("li", {}, seccion)));
  }
  selectTipo.addEventListener("change", pintarSecciones);
  pintarSecciones();

  const area = h("textarea", {
    className: "resumen",
    rows: 18,
    value: reunion.texto_resumido || "",
    "aria-label": "Resumen de la reunión",
  });

  const guardar = h(
    "button",
    {
      className: "boton secundario",
      onclick: async () => {
        try {
          await api(`/reuniones/${id}/resumen`, { metodo: "PUT", cuerpo: { texto: area.value } });
          toast("Resumen guardado. La versión anterior queda en el historial.", "ok");
        } catch (error) {
          toast(error.message, "error");
        }
      },
    },
    "Guardar cambios"
  );

  const regenerar = h(
    "button",
    {
      className: "boton",
      onclick: async (evento) => {
        const boton = evento.currentTarget;
        boton.disabled = true;
        boton.textContent = "Regenerando…";
        try {
          const resultado = await api(`/reuniones/${id}/resumen/regenerar`, {
            metodo: "POST",
            cuerpo: { tipo: selectTipo.value },
          });
          area.value = resultado.texto_resumido;
          toast("Resumen regenerado", "ok");
        } catch (error) {
          toast(error.message, "error");
        } finally {
          boton.disabled = false;
          boton.textContent = "Regenerar con este tipo";
        }
      },
    },
    "Regenerar con este tipo"
  );

  return h(
    "section",
    { className: "panel" },
    h("div", { className: "fila" }, h("label", {}, "Tipo de reunión", selectTipo)),
    h("div", { className: "ayuda-bloque" }, h("span", { className: "ayuda" }, "Apartados del resumen:"), secciones),
    area,
    h("div", { className: "acciones" }, regenerar, guardar)
  );
}

async function panelTemas(id) {
  const temas = await api(`/reuniones/${id}/temas`);

  const extraer = h(
    "button",
    {
      className: "boton secundario",
      onclick: async (evento) => {
        const boton = evento.currentTarget;
        boton.disabled = true;
        try {
          const resultado = await api(`/reuniones/${id}/temas/extraer`, { metodo: "POST" });
          toast(`${resultado.temas} temas registrados`, "ok");
          recargar();
        } catch (error) {
          toast(error.message, "error");
          boton.disabled = false;
        }
      },
    },
    "Volver a extraer temas"
  );

  if (!temas.length) {
    return h(
      "section",
      { className: "panel" },
      vacio("No se han detectado temas en esta reunión."),
      h("div", { className: "acciones" }, extraer)
    );
  }

  return h(
    "section",
    { className: "panel" },
    h("div", { className: "acciones" }, extraer),
    h(
      "div",
      { className: "lista-tarjetas" },
      temas.map((tema) => {
        const anteriores = tema.veces_mencionado - 1;
        const historial =
          anteriores > 0
            ? ` · ya tratado en ${anteriores} reunión(es) anteriores; primera vez hace ${tema.dias_desde_primera} días`
            : " · primera vez que aparece";
        return h(
          "article",
          { className: "tarjeta" },
          h(
            "div",
            { className: "tarjeta-cabecera" },
            h("a", { className: "titulo", href: `#/temas/${tema.id}` }, tema.titulo),
            badgeEstado(tema.estado_en_esta_reunion)
          ),
          h("p", {}, tema.descripcion),
          h("p", { className: "ayuda" }, `Minuto ${tema.minuto_en_esta_reunion}${historial}`),
          h("div", { className: "badges" }, badgesAlerta(tema.alertas))
        );
      })
    )
  );
}

async function panelExportar(id) {
  const [destinos, historial] = await Promise.all([
    api("/destinos"),
    api(`/reuniones/${id}/exportaciones`),
  ]);
  const email = destinos.find((destino) => destino.id === "email");
  const slack = destinos.find((destino) => destino.id === "slack");

  const destinatarios = [];
  const chips = h("div", { className: "chips" });
  const campo = h("input", {
    type: "email",
    "aria-label": "Correo de la persona destinataria",
    placeholder: "correo@empresa.com (Enter para añadir)",
  });
  const incluirTemas = h("input", { type: "checkbox", checked: true });
  const historialBox = h("div", {});

  function pintarChips() {
    chips.replaceChildren(
      ...destinatarios.map((correo, indice) =>
        h(
          "span",
          { className: "chip" },
          correo,
          " ",
          h(
            "button",
            {
              className: "enlace",
              "aria-label": `Quitar a ${correo} de los destinatarios`,
              onclick: () => {
                destinatarios.splice(indice, 1);
                pintarChips();
              },
            },
            "×"
          )
        )
      )
    );
  }

  function anadirCorreo() {
    const correo = campo.value.trim();
    if (!correo) return true;
    if (!EMAIL.test(correo)) {
      toast(`Email no válido: ${correo}`, "error");
      return false;
    }
    if (!destinatarios.includes(correo)) destinatarios.push(correo);
    campo.value = "";
    pintarChips();
    return true;
  }

  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === ",") {
      evento.preventDefault();
      anadirCorreo();
    }
  });

  function pintarHistorial(lista) {
    historialBox.replaceChildren(
      lista.length
        ? h(
            "table",
            { className: "tabla" },
            h(
              "thead",
              {},
              h("tr", {}, h("th", {}, "Fecha"), h("th", {}, "Destino"), h("th", {}, "Para"), h("th", {}, "Resultado"))
            ),
            h(
              "tbody",
              {},
              lista.map((envio) =>
                h(
                  "tr",
                  {},
                  h("td", {}, formatearFechaHora(envio.created_at)),
                  h("td", {}, envio.destino === "email" ? "Email" : "Slack"),
                  h("td", {}, envio.destinatario),
                  h(
                    "td",
                    {},
                    envio.estado === "enviado"
                      ? h("span", { className: "badge alerta-ok" }, "Enviado")
                      : h("span", { className: "badge alerta-antiguo" }, "Error"),
                    envio.detalle ? h("span", { className: "ayuda" }, " " + envio.detalle) : null
                  )
                )
              )
            )
          )
        : vacio("Sin envíos todavía.")
    );
  }

  async function enviar(destino, boton) {
    if (destino === "email") {
      if (!anadirCorreo()) return;
      if (!destinatarios.length) {
        toast("Indica al menos un destinatario", "error");
        return;
      }
    }

    boton.disabled = true;
    try {
      await api(`/reuniones/${id}/exportar`, {
        metodo: "POST",
        cuerpo: {
          destino,
          destinatarios: destino === "email" ? [...destinatarios] : [],
          incluir_temas: incluirTemas.checked,
        },
      });
      toast(destino === "email" ? "Resumen enviado por email" : "Resumen publicado en Slack", "ok");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      boton.disabled = false;
    }

    try {
      pintarHistorial(await api(`/reuniones/${id}/exportaciones`));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  pintarChips();
  pintarHistorial(historial);

  return h(
    "section",
    { className: "panel exportar" },
    h("label", { className: "casilla" }, incluirTemas, " Incluir temas y su historial"),
    h(
      "section",
      {},
      h("h3", {}, "Email"),
      email?.configurado
        ? null
        : h("p", { className: "ayuda" }, "Sin configurar. Añade SMTP_HOST y SMTP_FROM en .env."),
      h("div", { className: "chips-entrada" }, chips, campo),
      h(
        "div",
        { className: "acciones" },
        h(
          "button",
          {
            className: "boton",
            disabled: !email?.configurado,
            onclick: (evento) => enviar("email", evento.currentTarget),
          },
          "Enviar por email"
        )
      )
    ),
    h(
      "section",
      {},
      h("h3", {}, "Slack"),
      slack?.configurado
        ? null
        : h("p", { className: "ayuda" }, "Sin configurar. Añade SLACK_WEBHOOK_URL en .env."),
      h(
        "div",
        { className: "acciones" },
        h(
          "button",
          {
            className: "boton",
            disabled: !slack?.configurado,
            onclick: (evento) => enviar("slack", evento.currentTarget),
          },
          "Publicar en Slack"
        )
      )
    ),
    h("section", {}, h("h3", {}, "Historial de envíos"), historialBox)
  );
}

async function panelVersiones(id) {
  const versiones = await api(`/reuniones/${id}/versiones`);
  if (!versiones.length) {
    return h("section", { className: "panel" }, vacio("Todavía no hay cambios guardados."));
  }

  return h(
    "section",
    { className: "panel" },
    h(
      "p",
      { className: "ayuda" },
      "Cada cambio guarda la versión anterior. Al restaurar, la versión actual también se guarda antes."
    ),
    h(
      "table",
      { className: "tabla" },
      h(
        "thead",
        {},
        h("tr", {}, h("th", {}, "Fecha"), h("th", {}, "Qué cambió"), h("th", {}, "Motivo"), h("th", {}))
      ),
      h(
        "tbody",
        {},
        versiones.map((version) =>
          h(
            "tr",
            {},
            h("td", {}, formatearFechaHora(version.created_at)),
            h("td", {}, ETIQUETAS_CAMPO[version.campo] || version.campo),
            h("td", {}, ETIQUETAS_ORIGEN[version.origen] || version.origen),
            h(
              "td",
              { className: "derecha" },
              h(
                "button",
                {
                  className: "boton secundario pequeno",
                  onclick: async () => {
                    if (!confirm("¿Restaurar esta versión? La versión actual se guardará antes.")) return;
                    try {
                      await api(`/reuniones/${id}/versiones/${version.id}/restaurar`, { metodo: "POST" });
                      toast("Versión restaurada", "ok");
                      recargar();
                    } catch (error) {
                      toast(error.message, "error");
                    }
                  },
                },
                "Restaurar"
              )
            )
          )
        )
      )
    )
  );
}

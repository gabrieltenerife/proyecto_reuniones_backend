// Configuración del backend y comprobación de conectividad.
import { api, guardarAjustes, obtenerAjustes, obtenerToken } from "../api.js";
import { h, toast } from "../ui.js";

export async function mostrarAjustes(contenedor) {
  const actuales = obtenerAjustes();
  const estado = h("div", { className: "estado-conexion", "aria-live": "polite" });
  const campoUrl = h("input", {
    type: "url",
    value: actuales.apiUrl,
    required: true,
    autocomplete: "url",
    placeholder: "http://localhost:8000",
  });

  async function probar() {
    estado.replaceChildren(h("p", { className: "cargando" }, "Comprobando conexión…"));
    try {
      const [tipos, destinos] = await Promise.all([api("/tipos"), api("/destinos")]);
      estado.replaceChildren(
        h("p", { className: "ok", role: "status" }, `Conexión correcta · ${tipos.length} tipos de reunión disponibles.`),
        h("p", { className: "ayuda" }, "Destinos de exportación"),
        h(
          "ul",
          { className: "lista-simple" },
          destinos.map((destino) =>
            h(
              "li",
              {},
              `${destino.nombre}: `,
              h(
                "span",
                { className: `badge ${destino.configurado ? "alerta-ok" : ""}` },
                destino.configurado ? "Configurado" : "Sin configurar"
              )
            )
          )
        )
      );
    } catch (error) {
      estado.replaceChildren(h("p", { className: "error", role: "alert" }, error.message));
    }
  }

  const formulario = h(
    "form",
    {
      className: "panel formulario ajustes-formulario",
      onsubmit: async (evento) => {
        evento.preventDefault();
        const urlNueva = campoUrl.value.trim().replace(/\/$/, "");
        const urlAnterior = actuales.apiUrl.replace(/\/$/, "");
        guardarAjustes({ apiUrl: urlNueva });
        toast("URL guardada", "ok");
        if (urlNueva !== urlAnterior) {
          estado.replaceChildren(
            h("p", { className: "aviso", role: "status" }, "La URL cambió. Inicia sesión de nuevo para conectar con ese backend.")
          );
          window.dispatchEvent(new Event("sesion-caducada"));
          return;
        }
        await probar();
      },
    },
    h("label", { for: campoUrl.id || "url-api" }, "URL del backend", campoUrl),
    h(
      "p",
      { className: "ayuda" },
      "Para el entorno local usa http://localhost:8000. El backend debe permitir el origen del frontend en CORS_ORIGINS."
    ),
    h("div", { className: "acciones" },
      h("button", { type: "submit", className: "boton" }, "Guardar y comprobar")
    )
  );
  campoUrl.id = "url-api";

  contenedor.replaceChildren(
    h("header", { className: "cabecera" },
      h("div", {},
        h("p", { className: "sobrelinea" }, "PREFERENCIAS"),
        h("h1", {}, "Ajustes"),
        h("p", { className: "subtitulo" }, "Administra la conexión de este espacio de trabajo.")
      )
    ),
    formulario,
    estado
  );

  if (obtenerToken()) await probar();
}

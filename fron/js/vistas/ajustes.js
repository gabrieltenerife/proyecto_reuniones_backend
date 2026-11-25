import { api, guardarAjustes, obtenerAjustes } from "../api.js";
import { h, toast } from "../ui.js";

export async function mostrarAjustes(contenedor) {
  const actuales = obtenerAjustes();
  const estado = h("div", { className: "estado-conexion" });

  const campoUrl = h("input", { type: "url", value: actuales.apiUrl, required: true });
  const campoClave = h("input", { type: "password", value: actuales.apiKey, autocomplete: "off" });

  async function probar() {
    estado.replaceChildren(h("p", { className: "cargando" }, "Probando conexión…"));
    try {
      const [tipos, destinos] = await Promise.all([api("/tipos"), api("/destinos")]);
      estado.replaceChildren(
        h("p", { className: "ok" }, `Conexión correcta: ${tipos.length} tipos de reunión disponibles.`),
        h("p", { className: "ayuda" }, "Destinos de exportación:"),
        h(
          "ul",
          { className: "lista-simple" },
          destinos.map((destino) =>
            h(
              "li",
              {},
              `${destino.nombre}: `,
              destino.configurado
                ? h("span", { className: "badge alerta-ok" }, "configurado")
                : h("span", { className: "badge" }, "sin configurar")
            )
          )
        )
      );
    } catch (error) {
      estado.replaceChildren(h("p", { className: "error" }, error.message));
    }
  }

  const formulario = h(
    "form",
    {
      className: "panel formulario",
      onsubmit: async (evento) => {
        evento.preventDefault();
        guardarAjustes({ apiUrl: campoUrl.value.trim(), apiKey: campoClave.value.trim() });
        toast("Ajustes guardados", "ok");
        await probar();
      },
    },
    h("label", {}, "URL de la API", campoUrl),
    h("label", {}, "Clave de API (X-API-Key, la de API_KEY_FRONT)", campoClave),
    h(
      "p",
      { className: "ayuda" },
      "La clave se guarda solo en este navegador. El backend debe incluir el origen de esta página en CORS_ORIGINS, por ejemplo http://localhost:3000."
    ),
    h("div", { className: "acciones" }, h("button", { type: "submit", className: "boton" }, "Guardar y probar"))
  );

  contenedor.replaceChildren(
    h("header", { className: "cabecera" }, h("h1", {}, "Ajustes")),
    formulario,
    estado
  );

  if (actuales.apiKey) {
    await probar();
  }
}

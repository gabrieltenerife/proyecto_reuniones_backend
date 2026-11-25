import { api } from "../api.js";
import { h, toast, formatearFecha, vacio } from "../ui.js";

export async function mostrarVocabulario(contenedor) {
  const terminos = await api("/vocabulario");

  const termino = h("input", { placeholder: "Término correcto, p. ej. Kubernetes", required: true });
  const variante = h("input", { placeholder: "Cómo se transcribe mal (opcional), p. ej. cuberneti" });

  const formulario = h(
    "form",
    {
      className: "panel formulario en-linea",
      onsubmit: async (evento) => {
        evento.preventDefault();
        try {
          await api("/vocabulario", {
            metodo: "POST",
            cuerpo: { termino: termino.value.trim(), variante: variante.value.trim() },
          });
          toast("Término guardado", "ok");
          window.dispatchEvent(new Event("recargar"));
        } catch (error) {
          toast(error.message, "error");
        }
      },
    },
    termino,
    variante,
    h("button", { type: "submit", className: "boton" }, "Añadir")
  );

  const tabla = terminos.length
    ? h(
        "table",
        { className: "tabla" },
        h(
          "thead",
          {},
          h("tr", {}, h("th", {}, "Término"), h("th", {}, "Se transcribe como"), h("th", {}, "Añadido"), h("th", {}))
        ),
        h(
          "tbody",
          {},
          terminos.map((fila) =>
            h(
              "tr",
              {},
              h("td", {}, fila.termino),
              h("td", {}, fila.variante || h("span", { className: "ayuda" }, "— (término propio)")),
              h("td", {}, formatearFecha(fila.created_at)),
              h(
                "td",
                { className: "derecha" },
                h(
                  "button",
                  {
                    className: "boton secundario pequeno",
                    onclick: async () => {
                      if (!confirm(`¿Eliminar "${fila.termino}"?`)) return;
                      try {
                        await api(`/vocabulario/${fila.id}`, { metodo: "DELETE" });
                        toast("Término eliminado", "ok");
                        window.dispatchEvent(new Event("recargar"));
                      } catch (error) {
                        toast(error.message, "error");
                      }
                    },
                  },
                  "Eliminar"
                )
              )
            )
          )
        )
      )
    : vacio("Todavía no hay vocabulario. Se añade al corregir una reunión o desde aquí.");

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h("h1", {}, "Vocabulario"),
      h("span", { className: "subtitulo" }, `${terminos.length} términos`)
    ),
    h("p", { className: "ayuda" }, "Nombres, siglas y términos técnicos. Se aplican a las transcripciones nuevas y se incluyen en los resúmenes."),
    formulario,
    h("div", { className: "tabla-contenedor" }, tabla)
  );
}

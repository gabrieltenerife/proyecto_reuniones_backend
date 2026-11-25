// Lista y detalle de temas abiertos, con alertas y seguimiento entre reuniones.
import { api } from "../api.js";
import {
  h,
  toast,
  formatearFecha,
  formatearMinuto,
  badgeEstado,
  badgesAlerta,
  vacio,
  cargando,
} from "../ui.js";

const ESTADOS = [
  ["", "Todos"],
  ["abierto", "Abiertos"],
  ["pospuesto", "Pospuestos"],
  ["resuelto", "Resueltos"],
];

let filtroActual = "";

function tarjetaTema(tema) {
  const menciones = tema.veces_mencionado;
  return h(
    "article",
    { className: "tarjeta" },
    h(
      "div",
      { className: "tarjeta-cabecera" },
      h("a", { className: "titulo", href: `#/temas/${tema.id}` }, tema.titulo),
      badgeEstado(tema.estado),
      badgesAlerta(tema.alertas)
    ),
    h("p", {}, tema.descripcion),
    h(
      "p",
      { className: "ayuda" },
      `${menciones} ${menciones === 1 ? "reunión" : "reuniones"}`,
      tema.dias_desde_primera ? ` · primera vez hace ${tema.dias_desde_primera} días` : " · primera vez hoy",
      tema.ultima_mencion ? ` · última: reunión #${tema.ultima_mencion.reunion_id}` : ""
    )
  );
}

export async function mostrarTemas(contenedor) {
  const selector = h(
    "select",
    {
      onchange: (evento) => {
        filtroActual = evento.currentTarget.value;
        cargarLista();
      },
    },
    ESTADOS.map(([valor, texto]) => h("option", { value: valor }, texto))
  );
  selector.value = filtroActual;

  const lista = h("div", { className: "lista-tarjetas" });

  async function cargarLista() {
    lista.replaceChildren(cargando());
    try {
      const temas = await api(`/temas${filtroActual ? `?estado=${filtroActual}` : ""}`);
      lista.replaceChildren(
        ...(temas.length ? temas.map(tarjetaTema) : [vacio("No hay temas con este filtro. Se detectan al procesar reuniones.")])
      );
    } catch (error) {
      lista.replaceChildren(h("p", { className: "error" }, error.message));
    }
  }

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h("h1", {}, "Temas"),
      h("span", { className: "subtitulo" }, "Asuntos que se repiten entre reuniones"),
      h("div", { className: "acciones" }, h("label", {}, "Estado ", selector))
    ),
    lista
  );

  await cargarLista();
}

export async function mostrarTema(contenedor, id) {
  const tema = await api(`/temas/${id}`);

  const selector = h(
    "select",
    {},
    ["abierto", "pospuesto", "resuelto"].map((estado) => h("option", { value: estado }, estado))
  );
  selector.value = tema.estado;
  selector.addEventListener("change", async () => {
    try {
      await api(`/temas/${id}`, { metodo: "PATCH", cuerpo: { estado: selector.value } });
      toast("Estado actualizado", "ok");
      window.dispatchEvent(new Event("recargar"));
    } catch (error) {
      toast(error.message, "error");
    }
  });

  contenedor.replaceChildren(
    h(
      "header",
      { className: "cabecera" },
      h(
        "div",
        {},
        h("a", { className: "migaja", href: "#/temas" }, "← Temas"),
        h("h1", {}, tema.titulo),
        h("span", { className: "subtitulo" }, tema.descripcion)
      ),
      h("div", { className: "acciones" }, h("label", {}, "Estado ", selector))
    ),
    h(
      "div",
      { className: "badges" },
      badgeEstado(tema.estado),
      badgesAlerta(tema.alertas),
      h(
        "span",
        { className: "ayuda" },
        `${tema.veces_mencionado} ${tema.veces_mencionado === 1 ? "mención" : "menciones"} · desde hace ${tema.dias_desde_primera} días`
      )
    ),
    h("h3", {}, "Historial"),
    h(
      "ol",
      { className: "linea-tiempo" },
      tema.menciones.map((mencion) =>
        h(
          "li",
          {},
          h(
            "div",
            { className: "linea-cabecera" },
            h("strong", {}, formatearFecha(mencion.reunion_fecha)),
            " · ",
            h(
              "a",
              { href: `#/reuniones/${mencion.reunion_id}?tab=temas` },
              `Reunión #${mencion.reunion_id}`
            ),
            ` · min ${formatearMinuto(mencion.segundos)} `,
            badgeEstado(mencion.estado)
          ),
          h("p", {}, mencion.resumen),
          h(
            "a",
            {
              className: "enlace-fuente",
              href: `#/reuniones/${mencion.reunion_id}?tab=transcripcion&min=${mencion.segundos}`,
            },
            "Ver en la transcripción"
          )
        )
      )
    )
  );
}

import { iniciarSesion, registrarCuenta } from "../api.js";
import { h } from "../ui.js";

export function mostrarAcceso(contenedor, alEntrar) {
  let modoRegistro = false;
  const correo = h("input", {
    id: "acceso-correo",
    type: "email",
    name: "email",
    autocomplete: "email",
    required: true,
    maxlength: 320,
    placeholder: "tu@empresa.com",
  });
  const password = h("input", {
    id: "acceso-password",
    type: "password",
    name: "password",
    autocomplete: "current-password",
    required: true,
    minlength: 1,
    maxlength: 256,
    "aria-describedby": "ayuda-password",
  });
  const ayudaPassword = h("span", { id: "ayuda-password", className: "ayuda" });
  const error = h("p", { className: "error acceso-error", role: "alert", hidden: true });
  const enviar = h("button", { type: "submit", className: "boton acceso-enviar" });
  const alternar = h("button", { type: "button", className: "enlace acceso-alternar" });
  const tituloPrincipal = h("h1", { id: "acceso-titulo" });
  const tituloPanel = h("h2", {});
  const descripcionTexto = h("p", { className: "subtitulo", id: "acceso-descripcion" });
  const formulario = h("form", { className: "formulario acceso-formulario" });

  function pintarModo() {
    const descripcion = modoRegistro
      ? "Registra una cuenta para guardar y consultar tus reuniones de forma privada."
      : "Transcripciones, acuerdos y seguimientos en un único lugar.";
    tituloPrincipal.textContent = modoRegistro ? "Empieza con buen pie." : "Reuniones, en orden.";
    tituloPanel.textContent = modoRegistro ? "Crea tu cuenta" : "Accede a tu cuenta";
    descripcionTexto.textContent = descripcion;
    password.autocomplete = modoRegistro ? "new-password" : "current-password";
    password.minLength = modoRegistro ? 12 : 1;
    password.placeholder = modoRegistro ? "Al menos 12 caracteres" : "Tu contraseña";
    ayudaPassword.textContent = modoRegistro
      ? "Usa al menos 12 caracteres."
      : "Tu sesión se mantiene mientras esta pestaña esté abierta.";
    enviar.textContent = modoRegistro ? "Crear cuenta" : "Iniciar sesión";
    alternar.textContent = modoRegistro
      ? "¿Ya tienes cuenta? Inicia sesión"
      : "¿Primera vez aquí? Crea una cuenta";
    error.hidden = true;

    formulario.replaceChildren(
      h("label", { for: correo.id }, "Correo electrónico", correo),
      h("label", { for: password.id }, "Contraseña", password, ayudaPassword),
      error,
      enviar,
      h("div", { className: "acceso-alternativa" }, alternar)
    );
    formulario.setAttribute("aria-label", modoRegistro ? "Crear cuenta" : "Iniciar sesión");
    alternar.onclick = () => {
      modoRegistro = !modoRegistro;
      pintarModo();
      password.value = "";
      (modoRegistro ? correo : password).focus();
    };
    formulario.onsubmit = async (evento) => {
      evento.preventDefault();
      error.hidden = true;
      enviar.disabled = true;
      enviar.textContent = "Conectando…";
      try {
        const usuario = modoRegistro
          ? await registrarCuenta(correo.value.trim(), password.value)
          : await iniciarSesion(correo.value.trim(), password.value);
        await alEntrar(usuario);
      } catch (fallo) {
        error.textContent = fallo.message;
        error.hidden = false;
      } finally {
        enviar.disabled = false;
        enviar.textContent = modoRegistro ? "Crear cuenta" : "Iniciar sesión";
      }
    };
  }

  pintarModo();
  contenedor.replaceChildren(
    h(
      "section",
      { className: "acceso-panel", "aria-labelledby": "acceso-titulo" },
      h(
        "div",
        { className: "acceso-marca" },
        h("span", { className: "marca-icono", "aria-hidden": "true" }, "R"),
        h("span", {}, "Reuniones")
      ),
      h("div", { className: "acceso-intro" },
        h("p", { className: "sobrelinea" }, "TU ESPACIO DE TRABAJO"),
        tituloPrincipal,
        descripcionTexto
      ),
      h("div", { className: "acceso-caja" },
        tituloPanel,
        h("p", { className: "ayuda" }, "Cada usuario solo ve sus propias reuniones."),
        formulario
      ),
      h("p", { className: "acceso-pie" }, "Acceso privado · Sesión protegida")
    )
  );
}

import { api } from "../api.js";
import { h, toast } from "../ui.js";

const LIMITE_FOTO = 350_000;

async function redimensionarFoto(archivo) {
  if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(archivo.type)) {
    throw new Error("Elige una imagen JPEG, PNG, WebP o GIF.");
  }
  if (archivo.size > 5 * 1024 * 1024) {
    throw new Error("La imagen debe pesar menos de 5 MB.");
  }

  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(archivo);
    const imagen = new Image();
    imagen.onload = () => {
      try {
        const escala = Math.min(1, 256 / Math.max(imagen.naturalWidth, imagen.naturalHeight));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(imagen.naturalWidth * escala));
        canvas.height = Math.max(1, Math.round(imagen.naturalHeight * escala));
        const contexto = canvas.getContext("2d");
        if (!contexto) throw new Error("No se pudo procesar la imagen.");
        contexto.drawImage(imagen, 0, 0, canvas.width, canvas.height);

        for (const calidad of [0.82, 0.72, 0.62]) {
          const datos = canvas.toDataURL("image/jpeg", calidad);
          if (datos.length <= LIMITE_FOTO) {
            resolve(datos);
            return;
          }
        }
        reject(new Error("No se pudo reducir la imagen lo suficiente. Prueba con otra foto."));
      } catch {
        reject(new Error("No se pudo procesar esa imagen. Prueba con otra foto."));
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    imagen.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("No se pudo abrir esa imagen."));
    };
    imagen.src = url;
  });
}

export async function abrirPerfil(alActualizar, alCambiarPassword) {
  const usuario = await api("/auth/me");
  const dialogo = h("dialog", {
    id: "dialog-perfil",
    className: "dialogo-perfil",
    "aria-labelledby": "perfil-titulo",
  });

  const vistaFoto = h("div", { className: "perfil-foto-vista" });
  const estadoFoto = h("p", { className: "ayuda", role: "status", "aria-live": "polite" });
  const archivoFoto = h("input", {
    className: "entrada-foto",
    type: "file",
    accept: "image/*",
    "aria-label": "Seleccionar una foto de perfil",
    onchange: async (evento) => {
      const archivo = evento.currentTarget.files?.[0];
      if (!archivo) return;
      try {
        fotoPendiente = await redimensionarFoto(archivo);
        pintarFoto(fotoPendiente);
        guardarFoto.disabled = false;
        estadoFoto.textContent = "Vista previa lista. Guarda para aplicar el cambio.";
      } catch (error) {
        estadoFoto.textContent = error.message;
        estadoFoto.setAttribute("role", "alert");
      }
    },
  });
  const guardarFoto = h("button", {
    type: "button",
    className: "boton",
    disabled: true,
    onclick: async () => {
      guardarFoto.disabled = true;
      estadoFoto.textContent = "Guardando foto…";
      try {
        const actualizado = await api("/auth/me", {
          metodo: "PATCH",
          cuerpo: { avatar_url: fotoPendiente },
        });
        usuario.avatar_url = actualizado.avatar_url;
        pintarFoto(usuario.avatar_url);
        alActualizar(usuario);
        estadoFoto.textContent = "Foto actualizada.";
        toast("Foto de perfil actualizada", "ok");
      } catch (error) {
        estadoFoto.textContent = error.message;
        estadoFoto.setAttribute("role", "alert");
        guardarFoto.disabled = false;
      }
    },
  }, "Guardar foto");
  const quitarFoto = h("button", {
    type: "button",
    className: "boton secundario",
    disabled: !usuario.avatar_url,
    onclick: () => {
      fotoPendiente = null;
      pintarFoto(null);
      guardarFoto.disabled = false;
      quitarFoto.disabled = true;
      estadoFoto.textContent = "La foto se quitará al guardar.";
      estadoFoto.setAttribute("role", "status");
    },
  }, "Quitar foto");
  let fotoPendiente = usuario.avatar_url || null;

  function pintarFoto(origen) {
    vistaFoto.replaceChildren(
      origen
        ? h("img", { src: origen, alt: `Foto de perfil de ${usuario.email}` })
        : h("span", { "aria-hidden": "true" }, (usuario.email?.[0] || "U").toLocaleUpperCase("es-ES"))
    );
    quitarFoto.disabled = !origen && !usuario.avatar_url;
  }
  pintarFoto(fotoPendiente);

  const actual = h("input", {
    type: "password",
    autocomplete: "current-password",
    required: true,
    maxlength: 256,
  });
  const nueva = h("input", {
    type: "password",
    autocomplete: "new-password",
    required: true,
    minlength: 12,
    maxlength: 256,
  });
  const confirmar = h("input", {
    type: "password",
    autocomplete: "new-password",
    required: true,
    minlength: 12,
    maxlength: 256,
  });
  const errorPassword = h("p", { className: "error", role: "alert", hidden: true });
  const cambiarPassword = h(
    "form",
    {
      className: "formulario perfil-password",
      onsubmit: async (evento) => {
        evento.preventDefault();
        errorPassword.hidden = true;
        if (nueva.value !== confirmar.value) {
          errorPassword.textContent = "Las contraseñas nuevas no coinciden.";
          errorPassword.hidden = false;
          confirmar.focus();
          return;
        }
        const boton = evento.currentTarget.querySelector('[type="submit"]');
        boton.disabled = true;
        boton.textContent = "Actualizando…";
        try {
          await api("/auth/change-password", {
            metodo: "POST",
            cuerpo: { password_actual: actual.value, password_nueva: nueva.value },
          });
          toast("Contraseña actualizada. Inicia sesión de nuevo.", "ok");
          dialogo.close();
          alCambiarPassword();
        } catch (error) {
          errorPassword.textContent = error.message;
          errorPassword.hidden = false;
          boton.disabled = false;
          boton.textContent = "Cambiar contraseña";
        }
      },
    },
    h("label", { for: "password-actual" }, "Contraseña actual", actual),
    h("label", { for: "password-nueva" }, "Contraseña nueva", nueva),
    h("label", { for: "password-confirmar" }, "Repite la contraseña nueva", confirmar),
    h("p", { className: "ayuda" }, "Debe tener al menos 12 caracteres. Al cambiarla, se cerrarán las demás sesiones."),
    errorPassword,
    h("button", { type: "submit", className: "boton" }, "Cambiar contraseña")
  );
  actual.id = "password-actual";
  nueva.id = "password-nueva";
  confirmar.id = "password-confirmar";

  const cerrar = h("button", {
    type: "button",
    className: "boton-cerrar-dialogo",
    "aria-label": "Cerrar configuración de perfil",
    onclick: () => dialogo.close(),
  }, "×");

  dialogo.append(
    h("header", { className: "dialogo-cabecera" },
      h("div", {},
        h("p", { className: "sobrelinea" }, "CUENTA"),
        h("h2", { id: "perfil-titulo" }, "Perfil y seguridad")
      ),
      cerrar
    ),
    h("section", { className: "perfil-seccion", "aria-labelledby": "perfil-datos-titulo" },
      h("h3", { id: "perfil-datos-titulo" }, "Datos básicos"),
      h("p", { className: "ayuda" }, "Correo de la cuenta"),
      h("p", { className: "perfil-correo" }, usuario.email),
      h("div", { className: "perfil-foto-controles" },
        vistaFoto,
        h("div", { className: "formulario" },
          h("label", { for: archivoFoto.id || "foto-perfil" }, "Foto de perfil", archivoFoto),
          h("p", { className: "ayuda" }, "Se guarda en tu cuenta. La imagen se ajusta a 256 × 256 px."),
          h("div", { className: "acciones" }, guardarFoto, quitarFoto),
          estadoFoto
        )
      )
    ),
    h("section", { className: "perfil-seccion", "aria-labelledby": "perfil-seguridad-titulo" },
      h("h3", { id: "perfil-seguridad-titulo" }, "Seguridad"),
      cambiarPassword
    )
  );
  archivoFoto.id = "foto-perfil";
  dialogo.addEventListener("close", () => dialogo.remove());
  dialogo.addEventListener("click", (evento) => {
    if (evento.target === dialogo) dialogo.close();
  });
  document.body.append(dialogo);
  dialogo.showModal();
  cerrar.focus();
}

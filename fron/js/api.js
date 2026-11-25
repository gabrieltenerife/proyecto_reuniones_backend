// Cliente HTTP: URL configurable y sesión bearer almacenada durante la pestaña.
const CLAVE_AJUSTES = "reuniones.ajustes";
const CLAVE_SESION = "reuniones.sesion";
const URL_POR_DEFECTO = "http://localhost:8000";

export class ApiError extends Error {
  constructor(mensaje, status) {
    super(mensaje);
    this.status = status;
  }
}

export function obtenerAjustes() {
  let guardados = {};
  try {
    guardados = JSON.parse(localStorage.getItem(CLAVE_AJUSTES) || "{}");
  } catch {
    guardados = {};
  }
  return { apiUrl: guardados.apiUrl || URL_POR_DEFECTO };
}

export function guardarAjustes(ajustes) {
  const urlAnterior = obtenerAjustes().apiUrl.replace(/\/$/, "");
  const apiUrl = ajustes.apiUrl.trim().replace(/\/$/, "");
  localStorage.setItem(CLAVE_AJUSTES, JSON.stringify({ apiUrl }));
  if (apiUrl !== urlAnterior) cerrarSesion();
}

export function obtenerToken() {
  const raw = sessionStorage.getItem(CLAVE_SESION);
  if (!raw) return "";
  try {
    const sesion = JSON.parse(raw);
    return sesion.apiUrl === obtenerAjustes().apiUrl.replace(/\/$/, "")
      ? sesion.accessToken
      : "";
  } catch {
    return "";
  }
}

export function cerrarSesion() {
  sessionStorage.removeItem(CLAVE_SESION);
}

async function leerRespuesta(respuesta) {
  const texto = await respuesta.text();
  let datos = null;
  try {
    datos = texto ? JSON.parse(texto) : null;
  } catch {
    datos = null;
  }
  if (!respuesta.ok) {
    const detalle = datos?.detail;
    const mensaje = typeof detalle === "string"
      ? detalle
      : Array.isArray(detalle)
        ? detalle.map((item) => item.msg).join("; ")
        : `Error ${respuesta.status}`;
    throw new ApiError(mensaje, respuesta.status);
  }
  return datos;
}

async function enviar(ruta, cuerpo) {
  const { apiUrl } = obtenerAjustes();
  const cabeceras = { "Content-Type": "application/json" };
  let respuesta;
  try {
    respuesta = await fetch(apiUrl.replace(/\/$/, "") + ruta, {
      method: "POST",
      headers: cabeceras,
      body: JSON.stringify(cuerpo),
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar. Comprueba que la API esté activa y que la URL y CORS estén configurados.",
      0
    );
  }
  return leerRespuesta(respuesta);
}

export async function iniciarSesion(email, password) {
  const datos = await enviar("/auth/login", { email, password });
  guardarSesion(datos);
  return datos.usuario;
}

export async function registrarCuenta(email, password) {
  const datos = await enviar("/auth/register", { email, password });
  guardarSesion(datos);
  return datos.usuario;
}

function guardarSesion(datos) {
  sessionStorage.setItem(
    CLAVE_SESION,
    JSON.stringify({
      accessToken: datos.access_token,
      apiUrl: obtenerAjustes().apiUrl.replace(/\/$/, ""),
    })
  );
}

export async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  const { apiUrl } = obtenerAjustes();
  const cabeceras = {};
  const token = obtenerToken();
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";

  let respuesta;
  try {
    respuesta = await fetch(apiUrl.replace(/\/$/, "") + ruta, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar. Comprueba que la API esté activa y que la URL y CORS estén configurados.",
      0
    );
  }

  if (respuesta.status === 204) return null;
  try {
    return await leerRespuesta(respuesta);
  } catch (error) {
    if (error.status === 401 && obtenerToken()) {
      cerrarSesion();
      window.dispatchEvent(new Event("sesion-caducada"));
    }
    throw error;
  }
}

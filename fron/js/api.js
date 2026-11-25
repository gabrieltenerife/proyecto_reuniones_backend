// Cliente HTTP común: URL, clave local/remota y errores de la API.
const CLAVE_AJUSTES = "reuniones.ajustes";
const URL_POR_DEFECTO = "http://localhost:8000";
const CLAVE_LOCAL = "local-test-key";

function esApiLocal(url) {
  try {
    return ["localhost", "127.0.0.1", "::1"].includes(new URL(url).hostname);
  } catch {
    return false;
  }
}

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

  const apiUrl = guardados.apiUrl || URL_POR_DEFECTO;
  // El backend de local/api_local.py tiene una clave fija de desarrollo.
  // Ignora claves antiguas guardadas en el navegador solo si el destino es local.
  const apiKey = esApiLocal(apiUrl) ? CLAVE_LOCAL : (guardados.apiKey || "");

  return {
    apiUrl,
    apiKey,
  };
}

export function guardarAjustes(ajustes) {
  localStorage.setItem(CLAVE_AJUSTES, JSON.stringify(ajustes));
}

function mensajeDeError(datos, status) {
  const detalle = datos?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) {
    return detalle.map((item) => item.msg).join("; ");
  }
  return `Error ${status}`;
}

export async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  const { apiUrl, apiKey } = obtenerAjustes();
  const cabeceras = { "X-API-Key": apiKey };
  if (cuerpo !== undefined) {
    cabeceras["Content-Type"] = "application/json";
  }

  let respuesta;
  try {
    respuesta = await fetch(apiUrl.replace(/\/$/, "") + ruta, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con la API. Revisa la URL en Ajustes y CORS_ORIGINS en el .env.",
      0
    );
  }

  if (respuesta.status === 204) return null;

  const texto = await respuesta.text();
  let datos = null;
  try {
    datos = texto ? JSON.parse(texto) : null;
  } catch {
    datos = null;
  }

  if (!respuesta.ok) {
    throw new ApiError(mensajeDeError(datos, respuesta.status), respuesta.status);
  }
  return datos;
}

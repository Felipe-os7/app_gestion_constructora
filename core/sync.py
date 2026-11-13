"""
Sincronización de estado entre varios equipos (p. ej. la misma aplicación abierta en 2 PC).

Dos capas complementarias:

1. REVISIÓN DEL ESTADO (servidor). ``compute_revision()`` resume en un hash corto el
   estado de proyectos, cuadrillas, trabajadores y solicitudes. Cualquier cambio
   (hecho desde cualquier PC) cambia el hash.

2. MIDDLEWARE (``LiveSyncMiddleware``), sin necesidad de editar plantillas:
   - Inyecta en las páginas de cuadrillas/trabajadores/reasignaciones un pequeño
     script que (a) agrega a cada formulario POST un campo oculto con la revisión
     con la que se dibujó la página y (b) consulta cada pocos segundos si el estado
     cambió. Si cambió y el usuario no está escribiendo, recarga la página; si está
     escribiendo, muestra un aviso para que decida cuándo actualizar.
   - Expone el endpoint ``/_sync/revision/`` (solo usuarios autenticados) que
     devuelve únicamente ``{"changed": bool, "revision": "<hash>"}``.

Al guardar, las vistas llaman a ``ensure_fresh(request)``: si el formulario se dibujó
con una revisión anterior (otro equipo ya cambió algo), se rechaza el guardado con un
mensaje claro y se recarga la información, en vez de pisar silenciosamente los
cambios del otro equipo.

IMPORTANTE: esto es consistencia para usuarios legítimos, NO una barrera de seguridad.
Quien manipule la petición puede omitir el campo; por eso la integridad real sigue
apoyándose en los bloqueos de fila (select_for_update) y las validaciones de las vistas.
"""
import hashlib
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse

SYNC_ENDPOINT = "/_sync/revision/"
SYNC_FIELD = "_sync_rev"
_REV_RE = re.compile(r"[0-9a-f]{16}")

MSG_DESINCRONIZADO = (
    "⚠️ Los datos fueron modificados desde otro equipo mientras trabajabas. "
    "Se cargó la información actualizada: revísala y vuelve a intentar."
)


def compute_revision():
    """Hash corto del estado compartido. Se ignora ``fecha_actualizacion`` (auto_now) para que un
    guardado sin cambios reales no genere falsas alertas."""
    from .models import Cuadrilla, Integrante, Proyecto, SolicitudReasignacion

    proyectos = list(Proyecto.objects.order_by("pk").values_list("pk", "nombre", "estado"))
    cuadrillas = list(
        Cuadrilla.objects.order_by("pk").values_list(
            "pk", "nombre", "estado", "proyecto_id", "trabajador_id",
            "jornada_inicio", "jornada_fin", "fecha_inicio_jornada", "fecha_fin_jornada", "horas_diarias",
        )
    )
    integrantes = list(
        Integrante.objects.order_by("pk").values_list(
            "pk", "usuario_id", "nombre_trabajador", "apellido_trabajador", "cargo", "especialidad",
            "estado", "cuadrilla_id", "licencia_inicio", "licencia_fin",
        )
    )
    solicitudes = list(
        SolicitudReasignacion.objects.order_by("-pk").values_list("pk", "estado")[:20]
    )
    resumen = repr((proyectos, cuadrillas, integrantes, solicitudes))
    return hashlib.sha256(resumen.encode()).hexdigest()[:16]


def ensure_fresh(request):
    """
    Lanza ValidationError si el formulario enviado se dibujó con datos que ya cambiaron.
    Si la petición no trae la revisión (JS desactivado, petición directa) no se bloquea:
    las validaciones de estado de cada vista siguen aplicando.
    """
    enviada = (request.POST.get(SYNC_FIELD) or "").strip()
    if enviada and enviada != compute_revision():
        raise ValidationError(MSG_DESINCRONIZADO)


# --------------------------------------------------------------------------- JS
_SCRIPT = """<script data-rev="{rev}" data-url="{url}" data-interval="{interval}" data-auto="{auto}" data-field="{field}">
(function () {{
  var s = document.currentScript, rev = s.dataset.rev, url = s.dataset.url, field = s.dataset.field;
  var every = Math.max(3, parseInt(s.dataset.interval, 10) || 8) * 1000, auto = s.dataset.auto === "1";
  function tag(f) {{
    if ((f.getAttribute("method") || "get").toLowerCase() !== "post") return;
    if (f.querySelector('input[name="' + field + '"]')) return;
    var i = document.createElement("input"); i.type = "hidden"; i.name = field; i.value = rev; f.appendChild(i);
  }}
  Array.prototype.forEach.call(document.querySelectorAll("form"), tag);
  document.addEventListener("submit", function (e) {{ tag(e.target); }}, true);
  var dirty = false, shown = false, busy = false;
  ["input", "change"].forEach(function (ev) {{ document.addEventListener(ev, function () {{ dirty = true; }}, true); }});
  function reload() {{ location.replace(location.pathname + location.search); }}
  function banner() {{
    var b = document.createElement("div");
    b.setAttribute("role", "alert");
    b.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:99999;padding:10px 16px;background:#fff3cd;" +
      "color:#664d03;border-bottom:1px solid #ffecb5;font:14px sans-serif;text-align:center";
    b.appendChild(document.createTextNode("Otro equipo modificó estos datos. Actualiza antes de guardar para no perder cambios. "));
    var btn = document.createElement("button"); btn.type = "button"; btn.textContent = "Actualizar ahora";
    btn.style.cssText = "margin-left:8px;padding:2px 10px;cursor:pointer"; btn.onclick = reload;
    b.appendChild(btn); document.body.appendChild(b);
  }}
  function check() {{
    if (shown || busy || document.hidden) return; busy = true;
    fetch(url + "?rev=" + encodeURIComponent(rev), {{credentials: "same-origin", cache: "no-store", headers: {{"Accept": "application/json"}}}})
      .then(function (r) {{ return r.ok ? r.json() : null; }})
      .then(function (d) {{
        busy = false;
        if (!d || !d.changed) return;
        if (auto && !dirty) {{ reload(); }} else {{ shown = true; banner(); }}
      }})
      .catch(function () {{ busy = false; }});
  }}
  setInterval(check, every);
  document.addEventListener("visibilitychange", check);
}})();
</script>"""


class LiveSyncMiddleware:
    """Colocar DESPUÉS de AuthenticationMiddleware y de SessionSecurityMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    # -- configuración -------------------------------------------------------
    @staticmethod
    def _enabled():
        return getattr(settings, "LIVE_SYNC_ENABLED", True)

    @staticmethod
    def _path_matches(path):
        exact = getattr(settings, "LIVE_SYNC_EXACT_PATHS", ("/",))
        prefixes = getattr(settings, "LIVE_SYNC_PATH_PREFIXES", ("/cuadrilla", "/reasign", "/trabajador", "/historial"))
        return path in exact or any(path.startswith(p) for p in prefixes)

    # -- flujo ---------------------------------------------------------------
    def __call__(self, request):
        if not self._enabled():
            return self.get_response(request)
        if request.path == SYNC_ENDPOINT:
            return self._endpoint(request)

        inyectar = (
            request.method in ("GET", "POST")
            and request.user.is_authenticated
            and self._path_matches(request.path)
        )
        # En GET la revisión se calcula ANTES de la vista: si algo cambia mientras se dibuja
        # la página, el peor caso es una recarga de más, nunca un cambio sin detectar.
        rev = compute_revision() if inyectar and request.method == "GET" else None
        response = self.get_response(request)
        if not inyectar or not self._es_html_inyectable(response):
            return response
        if rev is None:
            rev = compute_revision()
        return self._inyectar(request, response, rev)

    @staticmethod
    def _endpoint(request):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        if not request.user.is_authenticated:
            return JsonResponse({"error": "no autenticado"}, status=401)
        actual = compute_revision()
        enviada = request.GET.get("rev", "")
        response = JsonResponse({
            "changed": bool(_REV_RE.fullmatch(enviada)) and enviada != actual,
            "revision": actual,
        })
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def _es_html_inyectable(response):
        return (
            response.status_code == 200
            and not getattr(response, "streaming", False)
            and response.get("Content-Type", "").startswith("text/html")
            and not response.has_header("Content-Encoding")
        )

    @staticmethod
    def _inyectar(request, response, rev):
        html = response.content.decode(response.charset)
        posicion = html.rfind("</body>")
        if posicion == -1:
            return response
        script = _SCRIPT.format(
            rev=rev,
            url=SYNC_ENDPOINT,
            interval=int(getattr(settings, "LIVE_SYNC_INTERVAL_SECONDS", 8)),
            # Una página dibujada como respuesta a un POST (p. ej. el formulario de edición)
            # no se recarga sola: solo avisa, para no descartar lo que el usuario está haciendo.
            auto="1" if request.method == "GET" else "0",
            field=SYNC_FIELD,
        )
        response.content = html[:posicion] + script + html[posicion:]
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response

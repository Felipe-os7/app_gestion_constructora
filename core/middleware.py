"""
Middleware para verificar la integridad de la sesión del usuario.
Si se detectan cambios en el usuario (como desactivación, eliminación, etc.),
la sesión se cierra automáticamente por seguridad.
"""

import hashlib
import logging

from django.contrib.auth import logout
from django.shortcuts import redirect

from usuarios.models import PerfilUsuario
from core.models import Integrante

logger = logging.getLogger(__name__)

SESSION_HASH_KEY = "user_security_hash"


class SessionSecurityMiddleware:
    """
    Verifica en CADA petición (sin excepciones por ruta ni por método) que el
    usuario siga activo, con perfil activo y sin estar suspendido.

    Antes, los POST a /cuadrilla* se saltaban toda la verificación, de modo que
    un usuario suspendido o con perfil desactivado podía seguir operando con una
    sesión ya abierta. Ahora el hash solo incluye datos de seguridad (cuenta,
    rol y estado del perfil); los campos operativos del integrante (estado y
    cargo cambian al asignar a una cuadrilla) ya no invalidan la sesión, por lo
    que el bypass dejó de ser necesario. La suspensión se comprueba siempre,
    de forma explícita.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _get_user_hash(user, perfil):
        data = f"{user.pk}:{user.username}:{user.is_active}:{user.is_superuser}:{user.is_staff}"
        data += f":{perfil.estado}:{perfil.rol}" if perfil else ":no_perfil"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _invalidate(request):
        logout(request)  # flush de la sesión incluido
        return redirect("login")

    def __call__(self, request):
        # /admin tiene su propia autenticación; no se redirige al login de la app.
        if request.path.startswith("/admin"):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return self.get_response(request)

        try:
            # request.user ya se cargó desde la BD en esta petición y
            # ModelBackend ya descarta cuentas inactivas.
            user = request.user
            if not user.is_active:
                return self._invalidate(request)

            perfil = PerfilUsuario.objects.filter(usuario=user).first()
            if perfil is None or perfil.estado != "activo":
                return self._invalidate(request)

            if Integrante.objects.filter(usuario=user, estado="suspendido").exists():
                return self._invalidate(request)

            current_hash = self._get_user_hash(user, perfil)
            stored_hash = request.session.get(SESSION_HASH_KEY)
            if stored_hash is None:
                request.session[SESSION_HASH_KEY] = current_hash
            elif stored_hash != current_hash:
                return self._invalidate(request)
        except Exception:
            # Falla cerrada (más seguro), pero dejando rastro para diagnosticar.
            logger.exception("Error verificando la integridad de la sesión")
            return self._invalidate(request)

        return self.get_response(request)

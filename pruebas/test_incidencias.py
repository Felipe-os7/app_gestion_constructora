"""
Pruebas de seguridad del registro de incidencias (y su correo).

Ejecutar:  python manage.py test core.tests_incidencias
"""
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Cuadrilla, Incidencia, Integrante, Proyecto
from core.validators import validate_no_malicious_content

TEXTOS_MALICIOSOS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "java\nscript:alert(1)",
    "\uff1cscript\uff1e",                      # < > de ancho completo
    "visita http://malo.cl",
    "entra a www.malo.cl",
    "{{ 7*7 }}",
    "${jndi:ldap://x}",
    "&#60;script&#62;",
    "%3Cscript%3E",
    "%253Cscript%253E",                        # doble codificación
    "hola\nBcc: victima@example.com",          # inyección de cabeceras
    "union select password from auth_user",
    "../../etc/passwd",
    "data:text/html;base64,AAA",
    "algo onerror=alert(1)",
    "eval(x)",
]

TEXTOS_LEGITIMOS = [
    "Ausencia laboral",
    "El trabajador llegó 30 minutos tarde por la lluvia.",
    "Falta de materiales: cemento y arena (2 sacos)",
    "Se retiró a las 15:00 hrs.\nAvisó al jefe.",
]


class DetectorDeContenidoMaliciosoTests(TestCase):
    def test_rechaza_payloads_conocidos(self):
        for texto in TEXTOS_MALICIOSOS:
            with self.subTest(texto=texto), self.assertRaises(ValidationError):
                validate_no_malicious_content(texto)

    def test_acepta_texto_normal(self):
        for texto in TEXTOS_LEGITIMOS:
            with self.subTest(texto=texto):
                self.assertEqual(validate_no_malicious_content(texto), texto)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    INCIDENT_NOTIFICATION_EMAILS=["avisos@example.com"],
    INCIDENT_MAX_PER_MINUTE=3,
    INCIDENT_MAX_PER_MINUTE_GLOBAL=5,
    INCIDENT_DESCRIPTION_MAX_LENGTH=100,
)
class RegistroDeIncidenciasSeguroTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False
        self.lider = User.objects.create_user("lider", "lider@example.com", "UnaClaveSegura123!")
        self.proyecto = Proyecto.objects.create(
            nombre="Obra uno", cliente="Cliente", presupuesto=100,
            direccion="Direccion", ciudad="Santiago",
        )
        self.lider_int = Integrante.objects.create(usuario=self.lider, cargo="lider")
        self.cuadrilla = Cuadrilla.objects.create(
            nombre="Cuadrilla A", proyecto=self.proyecto, trabajador=self.lider_int,
        )
        self.url = reverse("registrar_incidencia")
        self.client.force_login(self.lider)

    def _enviar(self, descripcion="Atraso en la entrega", **extra):
        datos = {"cuadrilla": self.cuadrilla.id, "tipo": "otro", "descripcion": descripcion}
        datos.update(extra)
        return self.client.post(self.url, datos)

    def _no_se_guardo_ni_se_envio(self):
        self.assertFalse(Incidencia.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_contenido_malicioso_no_se_guarda_ni_se_envia(self):
        for texto in TEXTOS_MALICIOSOS:
            with self.subTest(texto=texto):
                r = self._enviar(texto)
                self.assertEqual(r.status_code, 302)
                self._no_se_guardo_ni_se_envio()

    def test_descripcion_demasiado_larga_es_rechazada(self):
        self._enviar("a" * 101)
        self._no_se_guardo_ni_se_envio()
        self._enviar("a" * 5000)
        self._no_se_guardo_ni_se_envio()

    def test_descripcion_demasiado_corta_o_con_demasiadas_lineas(self):
        self._enviar("abc")
        self._enviar("\n".join(["linea"] * 11))
        self._no_se_guardo_ni_se_envio()

    def test_descripcion_en_el_limite_es_aceptada_y_se_envia(self):
        r = self._enviar("a" * 100)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Incidencia.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\r", mail.outbox[0].subject)

    def test_limite_por_minuto_por_usuario(self):
        for _ in range(3):
            self._enviar()
        self.assertEqual(Incidencia.objects.count(), 3)
        self.assertEqual(len(mail.outbox), 3)

        self._enviar()  # cuarta en el mismo minuto
        self.assertEqual(Incidencia.objects.count(), 3)
        self.assertEqual(len(mail.outbox), 3)

    def test_limite_global_por_minuto(self):
        for i in range(3):
            otro = User.objects.create_user(f"otro{i}", f"otro{i}@example.com", "UnaClaveSegura123!")
            Incidencia.objects.create(
                cuadrilla=self.cuadrilla, tipo="otro", descripcion="Previa", registrado_por=otro,
            )
        for _ in range(2):
            Incidencia.objects.create(
                cuadrilla=self.cuadrilla, tipo="otro", descripcion="Previa", registrado_por=User.objects.get(username="otro0"),
            )
        self._enviar()  # ya hay 5 en el último minuto
        self.assertEqual(Incidencia.objects.count(), 5)
        self.assertEqual(len(mail.outbox), 0)

    def test_modelo_tambien_rechaza_contenido_malicioso(self):
        incidencia = Incidencia(
            cuadrilla=self.cuadrilla, tipo="otro", descripcion="<script>x</script>", registrado_por=self.lider,
        )
        with self.assertRaises(ValidationError):
            incidencia.full_clean()

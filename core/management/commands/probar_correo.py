"""
Diagnostico del correo: python manage.py probar_correo [destino@correo.com]

Muestra la configuracion efectiva (sin revelar el token) y envia un mensaje
de prueba, imprimiendo el detalle completo si falla.
"""
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envia un correo de prueba y muestra la configuracion de correo en uso."

    def add_arguments(self, parser):
        parser.add_argument(
            "destino",
            nargs="?",
            help="Correo de destino (por defecto, INCIDENT_NOTIFICATION_EMAILS).",
        )

    def handle(self, *args, **options):
        anymail = getattr(settings, "ANYMAIL", {})
        token = anymail.get("MAILTRAP_API_TOKEN", "")
        destinos = (
            [options["destino"]]
            if options["destino"]
            else list(settings.INCIDENT_NOTIFICATION_EMAILS)
        )

        self.stdout.write(f"EMAIL_BACKEND       : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL  : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(
            "Token configurado   : "
            + ("si (" + str(len(token)) + " caracteres)" if token else "NO")
        )
        self.stdout.write(
            "MAILTRAP_SANDBOX_ID : "
            + str(anymail.get("MAILTRAP_SANDBOX_ID", "(no definido: envio real)"))
        )
        self.stdout.write(f"Destinatarios       : {destinos or 'NINGUNO'}")
        if not destinos:
            self.stderr.write(
                "Indica un destino o define INCIDENT_NOTIFICATION_EMAILS en el .env."
            )
            return

        mensaje = EmailMessage(
            subject="Prueba de correo - Gestion de cuadrillas",
            body="Si lees esto, el envio por Mailtrap funciona.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=destinos,
        )
        mensaje.esp_extra = {"category": "Integration Test"}
        try:
            enviados = mensaje.send(fail_silently=False)
        except Exception as error:
            self.stderr.write(
                self.style.ERROR(
                    f"FALLO: {type(error).__name__}: {error}"
                )
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Enviado correctamente ({enviados})."))

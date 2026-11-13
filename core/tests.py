from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Cuadrilla, Incidencia, Integrante, Proyecto
from .validators import (
    validate_form_input_lengths,
    validate_person_name,
    validate_plain_text,
    validate_safe_text,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LogisticaCuadrillasTests(TestCase):
    def setUp(self):
        self.jefe = User.objects.create_user("jefe", "jefe@example.com", "UnaClaveSegura123!")
        self.jefe.perfil.rol = "jefe_obra"
        self.jefe.perfil.save()
        self.lider = User.objects.create_user("lider", "lider@example.com", "UnaClaveSegura123!")
        self.proyecto = Proyecto.objects.create(
            nombre="Obra de prueba", cliente="Cliente", presupuesto=100,
            direccion="Dirección", ciudad="Santiago",
        )
        self.lider_integrante = Integrante.objects.create(usuario=self.lider, cargo="lider")
        self.cuadrilla = Cuadrilla.objects.create(
            nombre="Cuadrilla A", proyecto=self.proyecto, trabajador=self.lider_integrante
        )

    def test_jornada_mayor_a_24_horas_es_invalida(self):
        self.cuadrilla.jornada_inicio = timezone.now()
        self.cuadrilla.jornada_fin = self.cuadrilla.jornada_inicio + timedelta(hours=25)
        with self.assertRaises(ValidationError):
            self.cuadrilla.full_clean()

    def test_jornada_con_dia_pasado_es_invalida(self):
        self.cuadrilla.fecha_inicio_jornada = timezone.localdate() - timedelta(days=1)
        self.cuadrilla.fecha_fin_jornada = timezone.localdate()
        self.cuadrilla.horas_diarias = Decimal("8")
        with self.assertRaises(ValidationError):
            self.cuadrilla.full_clean()

    def test_jornada_valida_acepta_dias_futuros_y_horas_diarias(self):
        for indice in range(3):
            Integrante.objects.create(
                nombre_trabajador=f"Jornada {indice}",
                apellido_trabajador="Prueba",
                cargo="operario",
                cuadrilla=self.cuadrilla,
            )
        self.cuadrilla.fecha_inicio_jornada = timezone.localdate()
        self.cuadrilla.fecha_fin_jornada = timezone.localdate() + timedelta(days=5)
        self.cuadrilla.horas_diarias = Decimal("8")
        self.cuadrilla.full_clean()

    def test_horas_diarias_deben_estar_entre_1_y_8(self):
        for horas in (Decimal("0.99"), Decimal("8.01")):
            self.cuadrilla.fecha_inicio_jornada = timezone.localdate()
            self.cuadrilla.fecha_fin_jornada = timezone.localdate()
            self.cuadrilla.horas_diarias = horas
            with self.assertRaises(ValidationError):
                self.cuadrilla.full_clean()

    def test_cuadrilla_debe_tener_entre_3_y_5_trabajadores(self):
        with self.assertRaises(ValidationError):
            self.cuadrilla.full_clean()

    def test_cuadrilla_no_puede_tener_dos_lideres(self):
        segundo_lider = Integrante.objects.create(
            nombre_trabajador="Segundo",
            apellido_trabajador="Líder",
            cargo="lider",
            cuadrilla=self.cuadrilla,
        )
        with self.assertRaises(ValidationError):
            self.cuadrilla.full_clean()

        segundo_lider.delete()

    def test_solo_una_cuenta_lider_puede_tener_cargo_lider(self):
        trabajador = Integrante.objects.create(
            nombre_trabajador="Trabajador",
            apellido_trabajador="Sin Cuenta",
            cargo="operario",
        )
        with self.assertRaises(ValidationError):
            trabajador.cargo = "lider"
            trabajador.full_clean()

        jefe = User.objects.create_user(
            "jefe-sin-lider",
            password="UnaClaveSegura123!",
        )
        jefe.perfil.rol = "jefe_obra"
        jefe.perfil.save()
        trabajador.usuario = jefe
        with self.assertRaises(ValidationError):
            trabajador.full_clean()

    def test_cuadrilla_no_puede_tener_dos_jefes_de_obra(self):
        supervisor = Integrante.objects.create(
            nombre_trabajador="Jefe",
            apellido_trabajador="Uno",
            cargo="supervisor",
            cuadrilla=self.cuadrilla,
        )
        otro_supervisor = Integrante(
            nombre_trabajador="Jefe",
            apellido_trabajador="Dos",
            cargo="supervisor",
            cuadrilla=self.cuadrilla,
        )
        with self.assertRaises(ValidationError):
            otro_supervisor.full_clean()

        supervisor.delete()
        trabajadores = [
            Integrante.objects.create(
                nombre_trabajador=f"Trabajador {indice}",
                apellido_trabajador="Prueba",
                cargo="operario",
                cuadrilla=self.cuadrilla,
            )
            for indice in range(3)
        ]
        self.cuadrilla.full_clean()
        Integrante.objects.create(
            nombre_trabajador="Trabajador 4",
            apellido_trabajador="Prueba",
            cargo="operario",
            cuadrilla=self.cuadrilla,
        )
        Integrante.objects.create(
            nombre_trabajador="Trabajador 5",
            apellido_trabajador="Prueba",
            cargo="operario",
            cuadrilla=self.cuadrilla,
        )
        self.cuadrilla.full_clean()
        Integrante.objects.create(
            nombre_trabajador="Trabajador 6",
            apellido_trabajador="Prueba",
            cargo="operario",
            cuadrilla=self.cuadrilla,
        )
        with self.assertRaises(ValidationError):
            self.cuadrilla.full_clean()

    def test_presupuesto_no_supera_mil_millones(self):
        proyecto = Proyecto(
            nombre="Proyecto sobre limite",
            cliente="Cliente",
            presupuesto=Proyecto.MAX_PRESUPUESTO + Decimal("0.01"),
            direccion="Dirección",
            ciudad="Santiago",
        )
        with self.assertRaises(ValidationError):
            proyecto.full_clean()

    def test_proyecto_debe_durar_al_menos_tres_semanas(self):
        proyecto = Proyecto(
            nombre="Proyecto corto",
            cliente="Cliente",
            fecha_inicio=timezone.localdate(),
            fecha_termino=timezone.localdate() + timedelta(days=20),
            presupuesto=100,
            direccion="Direccion",
            ciudad="Santiago",
        )
        with self.assertRaises(ValidationError):
            proyecto.full_clean()

    def test_proyecto_de_21_dias_es_valido(self):
        proyecto = Proyecto(
            nombre="Proyecto tres semanas",
            cliente="Cliente",
            fecha_inicio=timezone.localdate(),
            fecha_termino=timezone.localdate() + timedelta(days=21),
            presupuesto=100,
            direccion="Direccion",
            ciudad="Santiago",
        )
        proyecto.full_clean()

    def test_proyecto_no_acepta_fechas_pasadas(self):
        proyecto = Proyecto(
            nombre="Proyecto pasado",
            cliente="Cliente",
            fecha_inicio=timezone.localdate() - timedelta(days=1),
            presupuesto=100,
            direccion="Direccion",
            ciudad="Santiago",
        )
        with self.assertRaises(ValidationError):
            proyecto.full_clean()

    def test_jefe_puede_eliminar_proyecto_desde_la_lista(self):
        self.client.force_login(self.jefe)
        proyecto = Proyecto.objects.create(
            nombre="Proyecto eliminar",
            cliente="Cliente",
            fecha_inicio=timezone.localdate(),
            fecha_termino=timezone.localdate() + timedelta(days=21),
            presupuesto=100,
            direccion="Direccion",
            ciudad="Santiago",
        )
        response = self.client.post(
            f"/proyecto/eliminar/{proyecto.codigo}/",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Proyecto.objects.filter(pk=proyecto.codigo).exists())
        self.assertEqual(
            response.content.decode().count("Proyecto eliminado correctamente."),
            1,
        )

    def test_jefe_puede_eliminar_cuadrilla_con_un_solo_mensaje(self):
        self.client.force_login(self.jefe)
        response = self.client.post(
            f"/cuadrilla/eliminar/{self.cuadrilla.id}/",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Cuadrilla.objects.filter(pk=self.cuadrilla.id).exists())
        self.assertEqual(
            response.content.decode().count("Cuadrilla eliminada correctamente"),
            1,
        )

    def test_cuenta_lider_se_asigna_con_cargo_lider(self):
        user = User.objects.create_user(
            "lider-registro",
            password="UnaClaveSegura123!",
        )
        user.perfil.rol = "lider_cuadrilla"
        user.perfil.save()
        integrante = Integrante.objects.create(usuario=user, cargo="operario")
        integrante.cargo = "lider"
        integrante.full_clean()

    def test_lider_no_puede_modificar_cuadrilla(self):
        self.client.force_login(self.lider)
        response = self.client.post(
            "/cuadrilla/", {"nombre": "Otra", "proyecto": self.proyecto.codigo}
        )
        self.assertRedirects(response, "/cuadrilla/")
        self.assertFalse(Cuadrilla.objects.filter(nombre="Otra").exists())

    def test_incidencia_de_ausencia_envia_correo_al_jefe(self):
        self.client.force_login(self.lider)
        trabajador = Integrante.objects.create(
            nombre_trabajador="Ana", apellido_trabajador="Pérez",
            cargo="operario", cuadrilla=self.cuadrilla, estado="asignado",
        )
        response = self.client.post(
            "/incidencias/registrar/",
            {
                "cuadrilla": self.cuadrilla.id,
                "trabajador": trabajador.id,
                "tipo": "ausencia",
                "descripcion": "Ausencia laboral",
            },
        )
        self.assertRedirects(response, "/cuadrilla/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Ana Pérez", mail.outbox[0].body)
        self.assertTrue(Incidencia.objects.get().notificado)

    def test_texto_con_metacaracteres_sql_es_rechazado(self):
        for texto in ("'; DROP TABLE core_cuadrilla; --", "comentario /* SQL */"):
            with self.assertRaises(ValidationError):
                validate_safe_text(texto)

    def test_texto_normal_en_espanol_es_aceptado(self):
        self.assertEqual(
            validate_safe_text("Obra Ñandú, etapa 1 - sector norte."),
            "Obra Ñandú, etapa 1 - sector norte.",
        )

    def test_nombre_de_trabajador_rechaza_simbolos(self):
        for nombre in ("@asdasd", "Ana- María", "Ana.", "Ana'"):
            with self.assertRaises(ValidationError):
                validate_person_name(nombre)
        self.assertEqual(validate_person_name("Ana María"), "Ana María")

    def test_nombre_de_proyecto_y_cuadrilla_rechaza_simbolos(self):
        for texto in ("Obra-1", "Cuadrilla@", "Proyecto.", "Obra_1"):
            with self.assertRaises(ValidationError):
                validate_plain_text(texto)
        self.assertEqual(validate_plain_text("Obra 1"), "Obra 1")

    def test_formularios_rechazan_valores_mayores_a_20_caracteres(self):
        with self.assertRaises(ValidationError):
            validate_form_input_lengths(
                {"nombre": ["123456789012345678901"]}
            )

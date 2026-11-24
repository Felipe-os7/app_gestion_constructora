"""
Pruebas de manipulación de peticiones (estilo Burp Suite).

Cada prueba envía directamente al backend datos que el formulario HTML nunca
enviaría: IDs no numéricos, valores fuera de las opciones, NaN, fechas sin
zona horaria, saltos de línea, etc. Lo esperado es que la aplicación responda
con un rechazo controlado (redirect + mensaje), nunca con un error 500 ni
dejando datos inconsistentes.

Ejecutar:  python manage.py test core.tests_tampering
"""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Cuadrilla, Incidencia, Integrante, Proyecto, SolicitudReasignacion


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PeticionesManipuladasTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False
        self.hoy = timezone.localdate()

        self.jefe = User.objects.create_user("jefe", "jefe@example.com", "UnaClaveSegura123!")
        self.jefe.perfil.rol = "jefe_obra"
        self.jefe.perfil.save()

        self.lider = User.objects.create_user("lider", "lider@example.com", "UnaClaveSegura123!")
        self.lider_int = Integrante.objects.create(usuario=self.lider, cargo="lider")

        self.proyecto = Proyecto.objects.create(
            nombre="Obra uno", cliente="Cliente", presupuesto=100,
            direccion="Direccion", ciudad="Santiago",
        )
        self.cuadrilla = Cuadrilla.objects.create(
            nombre="Cuadrilla A", proyecto=self.proyecto, trabajador=self.lider_int,
        )
        self.lider_int.cuadrilla = self.cuadrilla
        self.lider_int.save()

    # ---------- utilidades ----------
    def _trabajadores(self, n, cuadrilla=None, prefijo="Trab"):
        return [
            Integrante.objects.create(
                nombre_trabajador=f"{prefijo}{chr(65 + i)}", apellido_trabajador="Prueba",
                cargo="operario", cuadrilla=cuadrilla,
                estado="asignado" if cuadrilla else "disponible",
            )
            for i in range(n)
        ]

    def _como_jefe(self):
        self.client.force_login(self.jefe)

    def _ok(self, response):
        self.assertLess(response.status_code, 500, "La petición manipulada produjo un error 500")

    # ---------- IDs no numéricos / inexistentes ----------
    def test_ids_no_numericos_no_producen_500(self):
        self._como_jefe()
        casos = [
            (reverse("cuadrilla"), {"accion": "reubicar", "integrante_id": "abc", "cuadrilla_destino": "1"}),
            (reverse("cuadrilla"), {"editar_cuadrilla": "abc"}),
            (reverse("cuadrilla"), {"nombre": "Nueva", "proyecto": "abc", "integrantes": ["1", "2", "3"]}),
            (reverse("cuadrilla"), {"nombre": "Nueva", "proyecto": self.proyecto.codigo,
                                    "integrantes": ["x", "y", "z"]}),
            (reverse("cuadrilla"), {"nombre": "Nueva", "proyecto": self.proyecto.codigo,
                                    "cuadrilla_id": "zzz", "integrantes": ["1", "2", "3"]}),
            (reverse("reasignacion"), {"accion": "crear_solicitud", "trabajador_id": "abc", "cuadrilla_destino": "1"}),
            (reverse("reasignacion"), {"accion": "responder_solicitud", "solicitud_id": "abc", "respuesta": "aceptar"}),
            (reverse("reasignacion"), {"accion": "agregar_noasignado", "trabajador_id": "9" * 40, "cuadrilla_destino": "1"}),
            (reverse("agregar_trabajador"), {"nombre_trabajador": "Ana", "apellido_trabajador": "Perez", "cuadrilla": "abc"}),
            (reverse("registrar_incidencia"), {"cuadrilla": "abc", "tipo": "otro", "descripcion": "x"}),
            (reverse("registrar_incidencia"), {"cuadrilla": str(self.cuadrilla.id), "trabajador": "abc",
                                               "tipo": "otro", "descripcion": "x"}),
            (reverse("editar_cuadrilla", args=[self.cuadrilla.id]),
             {"nombre": "Cuadrilla A", "proyecto": "abc", "integrantes": ["abc"]}),
            (reverse("editar_cuadrilla", args=[self.cuadrilla.id]),
             {"nombre": "Cuadrilla A", "proyecto": self.proyecto.codigo, "integrantes": ["99999"]}),
        ]
        for url, datos in casos:
            with self.subTest(url=url, datos=datos):
                self._ok(self.client.post(url, datos))

    def test_muchos_ids_en_una_peticion(self):
        self._como_jefe()
        r = self.client.post(reverse("cuadrilla"), {
            "nombre": "Flood", "proyecto": self.proyecto.codigo,
            "integrantes": [str(self.lider_int.id)] * 500,
        })
        self._ok(r)
        self.assertFalse(Cuadrilla.objects.filter(nombre="Flood").exists())

    # ---------- valores fuera de las opciones ----------
    def test_estado_de_proyecto_invalido_es_rechazado(self):
        self._como_jefe()
        self.client.post(reverse("proyecto"), {
            "nombre": "Proyecto estado", "cliente": "Cliente", "estado": "hackeado",
            "fecha_inicio": self.hoy.isoformat(),
            "fecha_termino": (self.hoy + timedelta(days=30)).isoformat(),
            "presupuesto": "100", "direccion": "Calle", "ciudad": "Santiago",
        })
        self.assertFalse(Proyecto.objects.filter(estado="hackeado").exists())

    def test_editar_proyecto_no_acepta_nombre_vacio_ni_estado_falso(self):
        self._como_jefe()
        proyecto = Proyecto.objects.create(
            nombre="Para editar", cliente="Cliente", presupuesto=100,
            direccion="Calle", ciudad="Santiago",
            fecha_inicio=self.hoy, fecha_termino=self.hoy + timedelta(days=30),
        )
        self.client.post(reverse("editar_proyecto", args=[proyecto.codigo]), {
            "nombre": "", "cliente": "Cliente", "estado": "hackeado",
            "fecha_inicio": self.hoy.isoformat(),
            "fecha_termino": (self.hoy + timedelta(days=30)).isoformat(),
            "presupuesto": "100", "direccion": "Calle", "ciudad": "Santiago",
        })
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nombre, "Para editar")
        self.assertNotEqual(proyecto.estado, "hackeado")

    def test_estado_de_cuadrilla_y_cargo_invalidos(self):
        self._como_jefe()
        trabajadores = self._trabajadores(3)
        self.client.post(reverse("cuadrilla"), {
            "nombre": "Estado falso", "proyecto": self.proyecto.codigo, "estado": "<script>",
            "integrantes": [t.id for t in trabajadores],
            "fecha_inicio_jornada": self.hoy.isoformat(),
            "fecha_fin_jornada": (self.hoy + timedelta(days=3)).isoformat(),
            "horas_diarias": "8",
        })
        self.assertFalse(Cuadrilla.objects.filter(nombre="Estado falso").exists())

        r = self.client.post(reverse("agregar_trabajador"), {
            "nombre_trabajador": "Ana", "apellido_trabajador": "Perez",
            "cargo": "dios", "especialidad": "hacker",
        })
        self._ok(r)
        self.assertFalse(Integrante.objects.filter(nombre_trabajador="Ana").exists())

    def test_respuesta_de_solicitud_invalida_no_cambia_nada(self):
        self._como_jefe()
        destino = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        trabajador = self._trabajadores(1, self.cuadrilla)[0]
        solicitud = SolicitudReasignacion.objects.create(
            trabajador=trabajador, cuadrilla_origen=self.cuadrilla, cuadrilla_destino=destino,
        )
        self.client.post(reverse("reasignacion"), {
            "accion": "responder_solicitud", "solicitud_id": solicitud.id, "respuesta": "lo-que-sea",
        })
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "pendiente")

    def test_incidencia_con_tipo_invalido_es_rechazada(self):
        self.client.force_login(self.lider)
        r = self.client.post(reverse("registrar_incidencia"), {
            "cuadrilla": self.cuadrilla.id, "tipo": "inventado", "descripcion": "Algo",
        })
        self._ok(r)
        self.assertFalse(Incidencia.objects.exists())

    # ---------- números y fechas ----------
    def test_presupuesto_nan_o_con_demasiados_decimales(self):
        self._como_jefe()
        base = {
            "cliente": "Cliente", "estado": "planificado",
            "fecha_inicio": self.hoy.isoformat(),
            "fecha_termino": (self.hoy + timedelta(days=30)).isoformat(),
            "direccion": "Calle", "ciudad": "Santiago",
        }
        for i, valor in enumerate(["NaN", "sNaN", "Infinity", "1e5", "1.999", "-1", "0"]):
            with self.subTest(valor=valor):
                r = self.client.post(reverse("proyecto"), {**base, "nombre": f"Pres {i}", "presupuesto": valor})
                self._ok(r)
                self.assertFalse(Proyecto.objects.filter(nombre=f"Pres {i}").exists())

    def test_horas_diarias_nan_o_fuera_de_rango(self):
        self._como_jefe()
        trabajadores = self._trabajadores(3)
        for i, horas in enumerate(["NaN", "9", "0.5", "1e1", "7.999"]):
            with self.subTest(horas=horas):
                r = self.client.post(reverse("cuadrilla"), {
                    "nombre": f"Horas {i}", "proyecto": self.proyecto.codigo,
                    "integrantes": [t.id for t in trabajadores],
                    "fecha_inicio_jornada": self.hoy.isoformat(),
                    "fecha_fin_jornada": (self.hoy + timedelta(days=3)).isoformat(),
                    "horas_diarias": horas,
                })
                self._ok(r)
                self.assertFalse(Cuadrilla.objects.filter(nombre=f"Horas {i}").exists())

    def test_jornada_con_datetime_sin_zona_horaria_no_rompe(self):
        self._como_jefe()
        trabajadores = self._trabajadores(3)
        manana = (timezone.now() + timedelta(days=1)).replace(tzinfo=None)
        r = self.client.post(reverse("cuadrilla"), {
            "nombre": "Jornada naive", "proyecto": self.proyecto.codigo,
            "integrantes": [t.id for t in trabajadores],
            "jornada_inicio": manana.isoformat(timespec="minutes"),
            "jornada_fin": (manana + timedelta(hours=8)).isoformat(timespec="minutes"),
            "fecha_inicio_jornada": self.hoy.isoformat(),
            "fecha_fin_jornada": (self.hoy + timedelta(days=3)).isoformat(),
            "horas_diarias": "8",
        })
        self._ok(r)

    def test_fechas_con_formatos_raros(self):
        self._como_jefe()
        for valor in ["2026-13-45", "20261112", "2026-W46-3", "٢٠٢٦-٠١-٠١", "9999-12-31", "'; --"]:
            with self.subTest(valor=valor):
                r = self.client.post(reverse("proyecto"), {
                    "nombre": "Fecha rara", "cliente": "Cliente", "estado": "planificado",
                    "fecha_inicio": valor, "fecha_termino": valor,
                    "presupuesto": "100", "direccion": "Calle", "ciudad": "Santiago",
                })
                self._ok(r)
                self.assertFalse(Proyecto.objects.filter(nombre="Fecha rara").exists())

    # ---------- texto ----------
    def test_nombre_con_salto_de_linea_es_rechazado(self):
        from core.validators import validate_plain_text, validate_person_name
        from django.core.exceptions import ValidationError
        for texto in ("Obra\n1", "Obra\t1", "Obra\r\nUno"):
            with self.subTest(texto=texto):
                with self.assertRaises(ValidationError):
                    validate_plain_text(texto)
                with self.assertRaises(ValidationError):
                    validate_person_name(texto.replace("1", "A").replace("Uno", "A"))

    def test_caracteres_de_control_unicode_son_rechazados(self):
        from core.validators import validate_safe_text
        from django.core.exceptions import ValidationError
        for texto in ("abc\u202edef", "abc\u200bdef", "abc\x7fdef", "abc\x85def", "abc\x00def"):
            with self.subTest(texto=repr(texto)):
                with self.assertRaises(ValidationError):
                    validate_safe_text(texto)

    # ---------- integridad / transacciones ----------
    def test_error_a_mitad_de_guardado_no_deja_cuadrilla_a_medias(self):
        self._como_jefe()
        otra = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        ocupado = self._trabajadores(1, otra, "Ocupado")[0]
        libres = self._trabajadores(2)
        r = self.client.post(reverse("cuadrilla"), {
            "nombre": "A medias", "proyecto": self.proyecto.codigo,
            "integrantes": [ocupado.id] + [t.id for t in libres],
            "fecha_inicio_jornada": self.hoy.isoformat(),
            "fecha_fin_jornada": (self.hoy + timedelta(days=3)).isoformat(),
            "horas_diarias": "8",
        })
        self._ok(r)
        self.assertFalse(Cuadrilla.objects.filter(nombre="A medias").exists())
        ocupado.refresh_from_db()
        self.assertEqual(ocupado.cuadrilla_id, otra.id)
        for t in libres:
            t.refresh_from_db()
            self.assertIsNone(t.cuadrilla_id)

    def test_editar_cuadrilla_no_permite_robar_integrantes_de_otra(self):
        self._como_jefe()
        otra = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        ajenos = self._trabajadores(3, otra, "Ajeno")
        self.client.post(reverse("editar_cuadrilla", args=[self.cuadrilla.id]), {
            "nombre": "Cuadrilla A", "proyecto": self.proyecto.codigo, "estado": "disponible",
            "integrantes": [t.id for t in ajenos],
        })
        for t in ajenos:
            t.refresh_from_db()
            self.assertEqual(t.cuadrilla_id, otra.id)

    def test_reubicar_a_cuadrilla_llena_es_rechazado(self):
        self._como_jefe()
        llena = Cuadrilla.objects.create(nombre="Llena", proyecto=self.proyecto)
        self._trabajadores(5, llena, "Lleno")
        extra = self._trabajadores(1, self.cuadrilla, "Extra")[0]
        self.client.post(reverse("cuadrilla"), {
            "accion": "reubicar", "integrante_id": extra.id, "cuadrilla_destino": llena.id,
        })
        extra.refresh_from_db()
        self.assertEqual(extra.cuadrilla_id, self.cuadrilla.id)
        self.assertEqual(llena.integrantes.count(), 5)

    def test_agregar_trabajador_no_excede_cinco_integrantes(self):
        self._como_jefe()
        llena = Cuadrilla.objects.create(nombre="Llena", proyecto=self.proyecto)
        self._trabajadores(5, llena, "Lleno")
        self.client.post(reverse("agregar_trabajador"), {
            "nombre_trabajador": "Sexto", "apellido_trabajador": "Trabajador",
            "cargo": "operario", "cuadrilla": llena.id,
        })
        self.assertEqual(llena.integrantes.count(), 5)

    def test_aceptar_solicitud_obsoleta_no_mueve_al_trabajador(self):
        self._como_jefe()
        destino = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        otra = Cuadrilla.objects.create(nombre="Cuadrilla C", proyecto=self.proyecto)
        trabajador = self._trabajadores(1, otra)[0]  # ya no está en cuadrilla_origen
        solicitud = SolicitudReasignacion.objects.create(
            trabajador=trabajador, cuadrilla_origen=self.cuadrilla, cuadrilla_destino=destino,
        )
        self.client.post(reverse("reasignacion"), {
            "accion": "responder_solicitud", "solicitud_id": solicitud.id, "respuesta": "aceptar",
        })
        trabajador.refresh_from_db()
        self.assertEqual(trabajador.cuadrilla_id, otra.id)

    # ---------- autorización ----------
    def test_lider_no_puede_registrar_incidencia_en_cuadrilla_ajena(self):
        otra = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        self.client.force_login(self.lider)
        r = self.client.post(reverse("registrar_incidencia"), {
            "cuadrilla": otra.id, "tipo": "otro", "descripcion": "Intento",
        })
        self._ok(r)
        self.assertFalse(Incidencia.objects.exists())

    def test_cuadrilla_sin_lider_no_rompe_a_un_lider(self):
        sin_lider = Cuadrilla.objects.create(nombre="Sin lider", proyecto=self.proyecto)
        self.client.force_login(self.lider)
        self._ok(self.client.get(reverse("ver_cuadrilla", args=[sin_lider.id])))
        self._ok(self.client.post(reverse("registrar_incidencia"), {
            "cuadrilla": sin_lider.id, "tipo": "otro", "descripcion": "Intento",
        }))
        self._ok(self.client.post(reverse("reasignacion"), {
            "accion": "crear_solicitud", "trabajador_id": self._trabajadores(1, sin_lider)[0].id,
            "cuadrilla_destino": self.cuadrilla.id,
        }))

    def test_integrante_suspendido_no_puede_postear_a_cuadrilla(self):
        """El middleware no debe dejar de verificar al usuario según la ruta."""
        self.lider_int.estado = "suspendido"
        self.lider_int.save()
        self.client.force_login(self.lider)
        r = self.client.post("/cuadrilla/", {"nombre": "x"})
        self.assertRedirects(r, "/usuarios/login/", fetch_redirect_response=False)

    def test_get_en_endpoints_de_eliminacion_no_borra(self):
        self._como_jefe()
        self.client.get(reverse("eliminar_cuadrilla", args=[self.cuadrilla.id]))
        self.client.get(reverse("eliminar_proyecto", args=[self.proyecto.codigo]))
        self.assertTrue(Cuadrilla.objects.filter(pk=self.cuadrilla.id).exists())
        self.assertTrue(Proyecto.objects.filter(pk=self.proyecto.codigo).exists())

    # ---------- robustez ----------
    def test_falla_del_correo_no_produce_500_ni_pierde_la_incidencia(self):
        self.client.force_login(self.lider)
        with mock.patch("django.core.mail.message.EmailMessage.send", side_effect=OSError("SMTP caído")):
            r = self.client.post(reverse("registrar_incidencia"), {
                "cuadrilla": self.cuadrilla.id, "tipo": "otro", "descripcion": "Prueba",
            })
        self._ok(r)
        incidencia = Incidencia.objects.get()
        self.assertFalse(incidencia.notificado)

    def test_exportacion_neutraliza_formulas_de_excel(self):
        from openpyxl import load_workbook
        Proyecto.objects.create(
            nombre="Con formula", cliente="=HYPERLINK(\"http://x\")", presupuesto=100,
            direccion="@SUM(1)", ciudad="Santiago",
        )
        self._como_jefe()
        r = self.client.get(reverse("exportar_excel"))
        self.assertEqual(r.status_code, 200)
        hoja = load_workbook(BytesIO(r.content)).active
        valores = [c.value for fila in hoja.iter_rows() for c in fila if isinstance(c.value, str)]
        self.assertFalse([v for v in valores if v[:1] in ("=", "@", "+", "-")])

    def test_camino_feliz_crear_cuadrilla(self):
        """Control: la validación estricta no debe romper el uso normal."""
        self._como_jefe()
        trabajadores = self._trabajadores(3)
        r = self.client.post(reverse("cuadrilla"), {
            "nombre": "Cuadrilla Nueva", "proyecto": self.proyecto.codigo, "estado": "disponible",
            "integrantes": [t.id for t in trabajadores],
            "fecha_inicio_jornada": self.hoy.isoformat(),
            "fecha_fin_jornada": (self.hoy + timedelta(days=5)).isoformat(),
            "horas_diarias": "7.5",
        })
        self.assertRedirects(r, reverse("cuadrilla"), fetch_redirect_response=False)
        nueva = Cuadrilla.objects.get(nombre="Cuadrilla Nueva")
        self.assertEqual(nueva.integrantes.count(), 3)
        self.assertEqual(nueva.horas_diarias, Decimal("7.5"))

    def test_camino_feliz_crear_proyecto(self):
        self._como_jefe()
        r = self.client.post(reverse("proyecto"), {
            "nombre": "Proyecto Valido", "cliente": "Cliente Uno", "estado": "planificado",
            "fecha_inicio": self.hoy.isoformat(),
            "fecha_termino": (self.hoy + timedelta(days=30)).isoformat(),
            "presupuesto": "1500000.50", "direccion": "Calle 1", "ciudad": "Santiago",
            "descripcion": "Ok",
        })
        self.assertRedirects(r, reverse("proyecto"), fetch_redirect_response=False)
        self.assertEqual(Proyecto.objects.get(nombre="Proyecto Valido").presupuesto, Decimal("1500000.50"))

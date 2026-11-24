"""
Pruebas de sincronización entre equipos: la misma aplicación abierta en dos PC
(dos clientes con sesiones independientes).

Ejecutar:  python manage.py test core.tests_sync
"""
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Cuadrilla, Integrante, Proyecto
from core.sync import SYNC_ENDPOINT, SYNC_FIELD, compute_revision

_REV_HTML = re.compile(r'data-rev="([0-9a-f]{16})"')


class BaseDosEquipos(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.jefe = User.objects.create_user("jefe", "jefe@example.com", "UnaClaveSegura123!")
        self.jefe.perfil.rol = "jefe_obra"
        self.jefe.perfil.save()
        self.jefe2 = User.objects.create_user("jefe2", "jefe2@example.com", "UnaClaveSegura123!")
        self.jefe2.perfil.rol = "jefe_obra"
        self.jefe2.perfil.save()

        self.pc_a, self.pc_b = Client(), Client()
        self.pc_a.force_login(self.jefe)
        self.pc_b.force_login(self.jefe2)

        self.proyecto = Proyecto.objects.create(
            nombre="Obra uno", cliente="Cliente", presupuesto=100, direccion="Dir", ciudad="Santiago",
        )
        self.cuad_a = Cuadrilla.objects.create(nombre="Cuadrilla A", proyecto=self.proyecto)
        self.cuad_b = Cuadrilla.objects.create(nombre="Cuadrilla B", proyecto=self.proyecto)
        lider = User.objects.create_user("lider", password="UnaClaveSegura123!")
        self.lider_int = Integrante.objects.create(usuario=lider, cargo="lider", cuadrilla=self.cuad_a, estado="asignado")
        self.cuad_a.trabajador = self.lider_int
        self.cuad_a.save()
        self.miembros = [self._trabajador(f"M{c}", self.cuad_a) for c in "AB"]
        self.libres = [self._trabajador(f"L{c}") for c in "ABC"]

    def _trabajador(self, nombre, cuadrilla=None):
        return Integrante.objects.create(
            nombre_trabajador=nombre, apellido_trabajador="Prueba", cargo="operario",
            cuadrilla=cuadrilla, estado="asignado" if cuadrilla else "disponible",
        )

    def _abrir(self, cliente, url):
        """Simula abrir la página en un PC: devuelve (respuesta, revisión con la que se dibujó)."""
        respuesta = cliente.get(url)
        self.assertEqual(respuesta.status_code, 200)
        coincidencia = _REV_HTML.search(respuesta.content.decode())
        self.assertIsNotNone(coincidencia, "la página no recibió el script de sincronización")
        return respuesta, coincidencia.group(1)

    def _mensajes(self, respuesta):
        return re.findall(r'<p class="msg">(.*?)</p>', respuesta.content.decode())

    def _datos_edicion(self, integrantes, rev=None):
        datos = {
            "nombre": "Cuadrilla A", "proyecto": self.proyecto.codigo, "estado": "disponible",
            "integrantes": [i.id for i in integrantes],
        }
        if rev:
            datos[SYNC_FIELD] = rev
        return datos


class RevisionDeEstadoTests(BaseDosEquipos):
    def test_es_estable_si_no_cambia_nada(self):
        self.assertEqual(compute_revision(), compute_revision())

    def test_un_guardado_sin_cambios_reales_no_la_altera(self):
        antes = compute_revision()
        self.miembros[0].save()  # auto_now actualiza fecha_actualizacion
        self.assertEqual(compute_revision(), antes)

    def test_cambia_al_asignar_un_trabajador(self):
        antes = compute_revision()
        self.libres[0].cuadrilla = self.cuad_b
        self.libres[0].estado = "asignado"
        self.libres[0].save()
        self.assertNotEqual(compute_revision(), antes)

    def test_cambia_con_estado_cargo_cuadrilla_y_proyecto(self):
        for modificar in (
            lambda: Integrante.objects.filter(pk=self.libres[0].pk).update(estado="licencia"),
            lambda: Integrante.objects.filter(pk=self.libres[0].pk).update(cargo="ayudante"),
            lambda: Cuadrilla.objects.filter(pk=self.cuad_b.pk).update(nombre="Cuadrilla Z"),
            lambda: Proyecto.objects.filter(pk=self.proyecto.pk).update(estado="en_progreso"),
        ):
            antes = compute_revision()
            modificar()
            self.assertNotEqual(compute_revision(), antes)


class EndpointDeRevisionTests(BaseDosEquipos):
    def test_requiere_autenticacion(self):
        self.assertEqual(Client().get(SYNC_ENDPOINT).status_code, 401)

    def test_informa_si_cambio_y_no_se_cachea(self):
        actual = compute_revision()
        r = self.pc_a.get(SYNC_ENDPOINT, {"rev": actual})
        self.assertEqual(r.json(), {"changed": False, "revision": actual})
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertTrue(self.pc_a.get(SYNC_ENDPOINT, {"rev": "0" * 16}).json()["changed"])

    def test_revision_invalida_o_ausente_no_produce_error(self):
        for rev in ("", "xyz", "G" * 16, "a" * 500, "' OR 1=1 --"):
            with self.subTest(rev=rev):
                r = self.pc_a.get(SYNC_ENDPOINT, {"rev": rev})
                self.assertEqual(r.status_code, 200)
                self.assertFalse(r.json()["changed"])

    def test_solo_acepta_get(self):
        self.assertEqual(self.pc_a.post(SYNC_ENDPOINT).status_code, 405)


class InyeccionDelScriptTests(BaseDosEquipos):
    def test_se_inyecta_en_paginas_de_cuadrillas_con_content_length_correcto(self):
        r, rev = self._abrir(self.pc_a, reverse("cuadrilla"))
        html = r.content.decode()
        self.assertLess(html.index("<script data-rev"), html.index("</body>"))
        self.assertIn('data-auto="1"', html)
        self.assertEqual(rev, compute_revision())
        if r.has_header("Content-Length"):
            self.assertEqual(int(r["Content-Length"]), len(r.content))

    def test_no_se_inyecta_fuera_de_las_paginas_configuradas_ni_a_anonimos(self):
        self.assertNotIn("data-rev", self.pc_a.get(reverse("proyecto")).content.decode())
        anonimo = Client().get(reverse("cuadrilla"))
        self.assertNotIn("data-rev", anonimo.content.decode())

    def test_pagina_dibujada_por_un_post_avisa_pero_no_se_recarga_sola(self):
        r = self.pc_a.post(reverse("cuadrilla"), {"editar_cuadrilla": self.cuad_a.id})
        self.assertIn('data-auto="0"', r.content.decode())

    @override_settings(LIVE_SYNC_ENABLED=False)
    def test_se_puede_desactivar(self):
        self.assertNotIn("data-rev", self.pc_a.get(reverse("cuadrilla")).content.decode())
        self.assertEqual(self.pc_a.get(SYNC_ENDPOINT).status_code, 404)


class DosEquiposEditandoATiempoTests(BaseDosEquipos):
    def test_reubicar_con_pantalla_vieja_es_rechazado_y_luego_funciona_al_actualizar(self):
        _, rev_a = self._abrir(self.pc_a, reverse("cuadrilla"))
        _, rev_b = self._abrir(self.pc_b, reverse("cuadrilla"))

        # El PC B asigna primero a un trabajador.
        r = self.pc_b.post(reverse("cuadrilla"), {
            "accion": "reubicar", "integrante_id": self.miembros[0].id,
            "cuadrilla_destino": self.cuad_b.id, SYNC_FIELD: rev_b,
        })
        self.assertEqual(r.status_code, 302)
        self.miembros[0].refresh_from_db()
        self.assertEqual(self.miembros[0].cuadrilla_id, self.cuad_b.id)

        # El PC A, con la pantalla anterior, intenta otro cambio: se rechaza sin tocar nada.
        r = self.pc_a.post(reverse("cuadrilla"), {
            "accion": "reubicar", "integrante_id": self.miembros[1].id,
            "cuadrilla_destino": self.cuad_b.id, SYNC_FIELD: rev_a,
        }, follow=True)
        self.assertTrue(any("otro equipo" in m for m in self._mensajes(r)))
        self.miembros[1].refresh_from_db()
        self.assertEqual(self.miembros[1].cuadrilla_id, self.cuad_a.id)

        # Tras la redirección la pantalla ya viene actualizada: el reintento sí funciona.
        nueva = _REV_HTML.search(r.content.decode()).group(1)
        self.assertEqual(nueva, compute_revision())
        r = self.pc_a.post(reverse("cuadrilla"), {
            "accion": "reubicar", "integrante_id": self.miembros[1].id,
            "cuadrilla_destino": self.cuad_b.id, SYNC_FIELD: nueva,
        })
        self.assertEqual(r.status_code, 302)
        self.miembros[1].refresh_from_db()
        self.assertEqual(self.miembros[1].cuadrilla_id, self.cuad_b.id)

    def test_actualizacion_perdida_al_editar_la_misma_cuadrilla(self):
        """Caso clásico: B agrega a alguien, A guarda su lista vieja y lo borraría sin aviso."""
        url_edicion = reverse("editar_cuadrilla", args=[self.cuad_a.id])
        _, rev_a = self._abrir(self.pc_a, url_edicion)
        _, rev_b = self._abrir(self.pc_b, url_edicion)
        base = [self.lider_int, *self.miembros]

        r = self.pc_b.post(url_edicion, self._datos_edicion(base + [self.libres[0]], rev_b))
        self.assertEqual(r.status_code, 302)
        self.libres[0].refresh_from_db()
        self.assertEqual(self.libres[0].cuadrilla_id, self.cuad_a.id)

        # A guarda su versión antigua (sin el trabajador que agregó B, y con otro distinto).
        r = self.pc_a.post(url_edicion, self._datos_edicion(base + [self.libres[1]], rev_a), follow=True)
        self.assertTrue(any("otro equipo" in m for m in self._mensajes(r)))
        self.libres[0].refresh_from_db()
        self.libres[1].refresh_from_db()
        self.assertEqual(self.libres[0].cuadrilla_id, self.cuad_a.id)   # lo de B se conserva
        self.assertIsNone(self.libres[1].cuadrilla_id)                  # lo de A no se aplicó

        # A recarga, ve lo de B y guarda con ambos cambios.
        nueva = _REV_HTML.search(r.content.decode()).group(1)
        r = self.pc_a.post(url_edicion, self._datos_edicion(base + [self.libres[0], self.libres[1]], nueva))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.cuad_a.integrantes.count(), 5)

    def test_doble_envio_del_mismo_formulario_se_bloquea(self):
        _, rev = self._abrir(self.pc_a, reverse("agregar_trabajador"))
        datos = {"nombre_trabajador": "Ana", "apellido_trabajador": "Perez", "cargo": "operario", SYNC_FIELD: rev}
        self.pc_a.post(reverse("agregar_trabajador"), datos)
        self.pc_a.post(reverse("agregar_trabajador"), datos)  # doble clic / reenvío
        self.assertEqual(Integrante.objects.filter(nombre_trabajador="Ana").count(), 1)

    def test_dos_equipos_asignando_al_mismo_trabajador_solo_uno_gana(self):
        _, rev_a = self._abrir(self.pc_a, reverse("cuadrilla"))
        _, rev_b = self._abrir(self.pc_b, reverse("cuadrilla"))
        libre = self.libres[0]
        # Incluso SIN token (por ejemplo con JS desactivado) el estado se valida en el servidor.
        r1 = self.pc_a.post(reverse("reasignacion"), {
            "accion": "agregar_noasignado", "trabajador_id": libre.id, "cuadrilla_destino": self.cuad_a.id})
        r2 = self.pc_b.post(reverse("reasignacion"), {
            "accion": "agregar_noasignado", "trabajador_id": libre.id, "cuadrilla_destino": self.cuad_b.id})
        self.assertEqual((r1.status_code, r2.status_code), (302, 302))
        libre.refresh_from_db()
        self.assertEqual(libre.cuadrilla_id, self.cuad_a.id)  # el segundo no lo movió

    def test_sin_token_el_guardado_sigue_permitido(self):
        """Compatibilidad: peticiones sin el campo (JS desactivado, scripts) no se bloquean."""
        r = self.pc_a.post(reverse("cuadrilla"), {
            "accion": "reubicar", "integrante_id": self.miembros[0].id, "cuadrilla_destino": self.cuad_b.id})
        self.assertEqual(r.status_code, 302)
        self.miembros[0].refresh_from_db()
        self.assertEqual(self.miembros[0].cuadrilla_id, self.cuad_b.id)

    def test_cambio_entre_la_comprobacion_y_la_escritura_revierte_todo(self):
        """Si otro equipo guarda justo después de la primera comprobación, la transacción se revierte."""
        datos = {
            "nombre": "Cuadrilla Nueva", "proyecto": self.proyecto.codigo,
            "integrantes": [t.id for t in self.libres],
            "fecha_inicio_jornada": self.hoy.isoformat(),
            "fecha_fin_jornada": (self.hoy + timedelta(days=3)).isoformat(),
            "horas_diarias": "8",
        }
        with mock.patch("core.views.ensure_fresh", side_effect=[None, ValidationError("cambió")]):
            self.pc_a.post(reverse("cuadrilla"), datos)
        self.assertFalse(Cuadrilla.objects.filter(nombre="Cuadrilla Nueva").exists())
        for t in self.libres:
            t.refresh_from_db()
            self.assertIsNone(t.cuadrilla_id)

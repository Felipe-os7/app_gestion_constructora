"""Página 404 personalizada.  Ejecutar: python manage.py test core.tests_errores"""
from django.test import TestCase


class Pagina404Tests(TestCase):
    def test_ruta_inexistente_muestra_la_pagina_404(self):
        r = self.client.get("/esta-ruta-no-existe/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Página no encontrada", status_code=404)
        self.assertContains(r, 'href="/"', status_code=404)

    def test_404_no_filtra_informacion_tecnica(self):
        r = self.client.get("/admin-secreto/../../etc/passwd")
        self.assertEqual(r.status_code, 404)
        self.assertNotContains(r, "Traceback", status_code=404)
        self.assertNotContains(r, "URLconf", status_code=404)

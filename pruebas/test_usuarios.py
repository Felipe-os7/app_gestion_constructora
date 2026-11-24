from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from usuarios.forms import CustomAuthenticationForm, RegistroUsuarioForm
from core.validators import validate_form_input_lengths


class RegistroUsuarioTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def datos_validos(self, rol):
        return {
            "username": "12345678-5",
            "first_name": "Persona",
            "last_name": "Prueba",
            "email": "persona@example.com",
            "rol": rol,
            "password1": "UnaClaveSegura123!",
            "password2": "UnaClaveSegura123!",
        }

    def test_registro_de_lider_crea_rol_y_cargo_correctos(self):
        form = RegistroUsuarioForm(data=self.datos_validos("lider_cuadrilla"))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.perfil.rol, "lider_cuadrilla")
        self.assertEqual(user.integrante.cargo, "lider")

    def test_registro_de_jefe_de_obra_crea_rol_y_cargo_correctos(self):
        form = RegistroUsuarioForm(data=self.datos_validos("jefe_obra"))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.perfil.rol, "jefe_obra")
        self.assertEqual(user.integrante.cargo, "supervisor")

    def test_registro_rechaza_simbolos_en_nombre(self):
        data = self.datos_validos("lider_cuadrilla")
        data["first_name"] = "@Persona"
        form = RegistroUsuarioForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("Solo se permiten letras", str(form.errors))

    def test_login_rechaza_usuario_con_simbolos(self):
        form = CustomAuthenticationForm(
            data={"username": "@usuario", "password": "Clave123!"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("RUT válido", str(form.errors))

    def test_registro_rechaza_puntos_en_rut(self):
        data = self.datos_validos("lider_cuadrilla")
        data["username"] = "12.345.678-5"
        form = RegistroUsuarioForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("RUT chileno válido", str(form.errors))

    def test_registro_acepta_email_de_hasta_40_caracteres(self):
        data = self.datos_validos("lider_cuadrilla")
        data["email"] = "persona.12345678901234567890@example.com"
        form = RegistroUsuarioForm(data=data)
        self.assertEqual(len(data["email"]), 40)
        self.assertTrue(form.is_valid(), form.errors)

    def test_registro_rechaza_email_de_mas_de_40_caracteres(self):
        data = self.datos_validos("lider_cuadrilla")
        data["email"] = "persona.123456789012345678901@example.com"
        form = RegistroUsuarioForm(data=data)
        self.assertGreater(len(data["email"]), 40)
        self.assertFalse(form.is_valid())
        self.assertIn("at most 40 characters", str(form.errors))

    def test_registro_rechaza_email_con_formato_invalido(self):
        data = self.datos_validos("lider_cuadrilla")
        data["email"] = "persona.12345678901234567890"
        form = RegistroUsuarioForm(data=data)
        self.assertLessEqual(len(data["email"]), 40)
        self.assertFalse(form.is_valid())
        self.assertIn("Enter a valid email address", str(form.errors))

    def test_registro_por_post_acepta_email_de_40_caracteres(self):
        data = self.datos_validos("lider_cuadrilla")
        data["email"] = "persona.12345678901234567890@example.com"
        response = self.client.post("/usuarios/registro/", data)
        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(email=data["email"]).exists())

    def test_validador_global_permite_email_hasta_40_caracteres(self):
        data = self.datos_validos("lider_cuadrilla")
        data["email"] = "persona.12345678901234567890@example.com"
        validate_form_input_lengths(data)

    def test_login_bloquea_sexto_intento_fallido(self):
        user = User.objects.create_user(
            username="12345678-5",
            password="UnaClaveSegura123!",
        )

        for _ in range(5):
            form = CustomAuthenticationForm(
                request=self.client.request().wsgi_request,
                data={"username": user.username, "password": "incorrecta"},
            )
            self.assertFalse(form.is_valid())

        form = CustomAuthenticationForm(
            request=self.client.request().wsgi_request,
            data={"username": user.username, "password": "UnaClaveSegura123!"},
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.rate_limit_exceeded)
        self.assertIn("15 minutos", str(form.non_field_errors()))

    def test_login_exitoso_limpia_el_limite(self):
        user = User.objects.create_user(
            username="12345678-5",
            password="UnaClaveSegura123!",
        )
        request = self.client.request().wsgi_request

        for _ in range(4):
            form = CustomAuthenticationForm(
                request=request,
                data={"username": user.username, "password": "incorrecta"},
            )
            self.assertFalse(form.is_valid())

        form = CustomAuthenticationForm(
            request=request,
            data={"username": user.username, "password": "UnaClaveSegura123!"},
        )
        self.assertTrue(form.is_valid(), form.errors)

        form = CustomAuthenticationForm(
            request=request,
            data={"username": user.username, "password": "incorrecta"},
        )
        self.assertFalse(form.is_valid())
        self.assertFalse(form.rate_limit_exceeded)

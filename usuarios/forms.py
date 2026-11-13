import hashlib
import re

from django import forms
from django.core.cache import cache
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import PerfilUsuario
from core.models import Integrante
from core.validators import MAX_FORM_INPUT_LENGTH, validate_person_name
from django.contrib.auth.forms import AuthenticationForm


LOGIN_RATE_LIMIT = 5
LOGIN_RATE_LIMIT_WINDOW = 15 * 60


class CustomAuthenticationForm(AuthenticationForm):
    """Bloquea el login de usuarios que estén en licencia."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limit_exceeded = False
        self._rate_limit_processed = False
        self.fields["username"].widget.attrs.update({
            "pattern": r"[0-9]{7,8}-[0-9Kk]",
            "data-rut": "true",
            "title": "Ingresa un RUT válido con formato 12345678-9.",
        })
        self.fields["password"].max_length = MAX_FORM_INPUT_LENGTH

    def _rate_limit_keys(self):
        username = self.data.get("username", "").strip().lower()
        remote_addr = (
            self.request.META.get("REMOTE_ADDR", "unknown")
            if self.request is not None
            else "unknown"
        )
        identifier = hashlib.sha256(
            f"{remote_addr}:{username}".encode("utf-8")
        ).hexdigest()
        ip_identifier = hashlib.sha256(
            remote_addr.encode("utf-8")
        ).hexdigest()
        return (
            f"login-failure:account:{identifier}",
            f"login-failure:ip:{ip_identifier}",
        )

    def _is_rate_limited(self):
        return any(
            (cache.get(key) or 0) >= LOGIN_RATE_LIMIT
            for key in self._rate_limit_keys()
        )

    def _register_failed_attempt(self):
        for key in self._rate_limit_keys():
            if not cache.add(key, 1, LOGIN_RATE_LIMIT_WINDOW):
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, LOGIN_RATE_LIMIT_WINDOW)

    def _clear_failed_attempts(self):
        cache.delete_many(self._rate_limit_keys())

    def is_valid(self):
        if self._rate_limit_processed:
            return self.errors == {}

        self._rate_limit_processed = True
        if self._is_rate_limited():
            self.rate_limit_exceeded = True
            self.add_error(
                None,
                (
                    "Demasiados intentos fallidos. "
                    "Espera 15 minutos antes de volver a intentar."
                ),
            )
            return False

        valid = super().is_valid()
        if valid:
            self._clear_failed_attempts()
        else:
            self._register_failed_attempt()
        return valid

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        try:
            integrante = user.integrante
            if integrante.estado == 'licencia':
                raise forms.ValidationError(
                    "Tu cuenta se encuentra en licencia y no puede iniciar sesión.",
                    code='inactive',
                )
        except Integrante.DoesNotExist:
            pass

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not RegistroUsuarioForm.validar_rut(username):
            raise forms.ValidationError(
                "Ingresa un RUT válido con formato 12345678-9."
            )
        return username


class RegistroUsuarioForm(UserCreationForm):
    """
    Formulario de registro de usuarios con selección de rol.
    """
    email = forms.EmailField(
        required=True,
        max_length=MAX_FORM_INPUT_LENGTH,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu correo electrónico'
        }),
        label="Correo electrónico"
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        validators=[validate_person_name],
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nombre",
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        validators=[validate_person_name],
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Apellido",
    )
    rol = forms.ChoiceField(
        choices=[
            ('lider_cuadrilla', 'Líder de Cuadrilla'),
            ('jefe_obra', 'Jefe de Obra'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label="Rol en el sistema",
        help_text="Selecciona el rol que tendrá la cuenta en el sistema.",
        initial='lider_cuadrilla'
    )
    cargo = forms.ChoiceField(
        choices=[
            ('lider', 'Líder de cuadrilla'),
            ('supervisor', 'Supervisor'),
        ],
        required=False,
        widget=forms.HiddenInput(),
        initial='lider'
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'rol')

    def clean_username(self):
        username = self.cleaned_data['username']
        if not self.validar_rut(username):
            raise forms.ValidationError("El nombre de usuario debe ser un RUT chileno válido (formato: 12345678-9)")
        return username

    @staticmethod
    def validar_rut(rut):
        """
        Valida el RUT chileno (formato: XXXXXXXX-Y)
        """
        rut = rut.strip()
        match = re.fullmatch(r'([0-9]{7,8})-([0-9Kk])', rut)
        if not match:
            return False
        cuerpo, dv = match.groups()
        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo = 9 if multiplo == 7 else multiplo + 1
            if multiplo > 7:
                multiplo = 2
        resto = suma % 11
        dv_calculado = 11 - resto
        if dv_calculado == 11:
            dv_final = '0'
        elif dv_calculado == 10:
            dv_final = 'K'
        else:
            dv_final = str(dv_calculado)
        return dv_final.lower() == dv.lower()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ingresa tu RUT(ej: 12345678-9)'
            ,'pattern': r'[0-9]{7,8}-[0-9Kk]'
            ,'data-rut': 'true'
        })
        self.fields['username'].help_text = 'El nombre de usuario debe ser un RUT válido (ejemplo: 12345678-9) y se usará para iniciar sesión.'
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ingresa tu contraseña',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirma tu contraseña',
        })
        self.fields['first_name'].max_length = MAX_FORM_INPUT_LENGTH
        self.fields['last_name'].max_length = MAX_FORM_INPUT_LENGTH
        self.fields['first_name'].widget.attrs['data-person-name'] = 'true'
        self.fields['last_name'].widget.attrs['data-person-name'] = 'true'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            rol = self.cleaned_data['rol']
            perfil, created = PerfilUsuario.objects.get_or_create(usuario=user)
            perfil.rol = rol
            perfil.save()
            user.perfil = perfil
            
            cargo = 'lider' if rol == 'lider_cuadrilla' else 'supervisor'
            integrante, _ = Integrante.objects.get_or_create(
                usuario=user,
                defaults={
                    'cargo': cargo,
                    'estado': 'disponible'
                }
            )
            if integrante.cargo != cargo:
                integrante.cargo = cargo
                integrante.save(update_fields=["cargo"])
        
        return user

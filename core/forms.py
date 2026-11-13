from django import forms
from .models import Proyecto, Cuadrilla, Incidencia
from .validators import validate_safe_text, validate_plain_text
from django.utils import timezone
from datetime import timedelta

# Una fecha absurdamente lejana (9999-12-31) no es un dato legítimo.
MAX_ANIOS_FUTURO = 20

class ProyectoForm(forms.ModelForm):
    nombre = forms.CharField(max_length=100, validators=[validate_safe_text, validate_plain_text])
    cliente = forms.CharField(max_length=100, validators=[validate_safe_text, validate_plain_text])
    direccion = forms.CharField(max_length=255, validators=[validate_safe_text])
    ciudad = forms.CharField(max_length=100, validators=[validate_safe_text])
    descripcion = forms.CharField(required=False, max_length=5000, validators=[validate_safe_text])
    class Meta:
        model = Proyecto
        fields = ['nombre', 'cliente', 'estado', 'fecha_inicio', 'fecha_termino',
                  'presupuesto', 'direccion', 'ciudad', 'descripcion']
    
    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        # Si estamos editando, excluir el proyecto actual de la validación
        qs = Proyecto.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError('Ya existe un proyecto con este nombre. Los nombres de proyectos deben ser únicos.')
        return nombre

    def _post_clean(self):
        # Si algún campo ya es inválido no se ejecuta Proyecto.clean() con datos parciales
        # (defensa adicional; el default de fecha_inicio ya es timezone.localdate).
        if self.errors:
            return
        super()._post_clean()

    def clean_presupuesto(self):
        presupuesto = self.cleaned_data["presupuesto"]
        if "e" in str(self.data.get("presupuesto", "")).lower():
            raise forms.ValidationError("El presupuesto debe ser un número válido.")
        if presupuesto > Proyecto.MAX_PRESUPUESTO:
            raise forms.ValidationError(
                "El presupuesto no puede superar $1.000.000.000."
            )
        return presupuesto

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get("fecha_inicio")
        termino = cleaned_data.get("fecha_termino")
        limite = timezone.localdate() + timedelta(days=365 * MAX_ANIOS_FUTURO)
        for campo, valor in (("fecha_inicio", inicio), ("fecha_termino", termino)):
            if valor and valor > limite:
                self.add_error(campo, "La fecha está fuera del rango permitido.")
        if inicio and inicio < timezone.localdate():
            self.add_error(
                "fecha_inicio",
                "La fecha de inicio no puede ser anterior a hoy.",
            )
        if termino and termino < timezone.localdate():
            self.add_error(
                "fecha_termino",
                "La fecha de término no puede ser anterior a hoy.",
            )
        if inicio and termino:
            if termino < inicio:
                self.add_error(
                    "fecha_termino",
                    "La fecha de término no puede ser anterior a la fecha de inicio.",
                )
            elif termino - inicio < Proyecto.MIN_DURACION:
                self.add_error(
                    "fecha_termino",
                    "El proyecto debe durar como mínimo 3 semanas.",
                )
        return cleaned_data

class CuadrillaForm(forms.ModelForm):
    nombre = forms.CharField(max_length=100, validators=[validate_safe_text, validate_plain_text])
    class Meta:
        model = Cuadrilla
        fields = [
            'nombre', 'proyecto', 'estado', 'fecha_inicio_jornada',
            'fecha_fin_jornada', 'horas_diarias',
        ]
        widgets = {
            'fecha_inicio_jornada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_jornada': forms.DateInput(attrs={'type': 'date'}),
            'horas_diarias': forms.NumberInput(attrs={'type': 'number', 'min': '1', 'max': '8', 'step': '0.25'}),
        }

    def clean_horas_diarias(self):
        horas = self.cleaned_data.get("horas_diarias")
        if horas is not None and not 1 <= horas <= 8:
            raise forms.ValidationError(
                "Las horas diarias deben estar entre 1 y 8 horas."
            )
        return horas

    def clean(self):
        cleaned_data = super().clean()
        hoy = timezone.localdate()
        for field_name in ("fecha_inicio_jornada", "fecha_fin_jornada"):
            fecha = cleaned_data.get(field_name)
            if fecha and fecha < hoy:
                self.add_error(
                    field_name,
                    "Las fechas de jornada no pueden ser anteriores a hoy.",
                )
        inicio = cleaned_data.get("fecha_inicio_jornada")
        termino = cleaned_data.get("fecha_fin_jornada")
        if inicio and termino and termino < inicio:
            self.add_error(
                "fecha_fin_jornada",
                "El último día no puede ser anterior al primer día.",
            )
        return cleaned_data


class IncidenciaForm(forms.ModelForm):
    descripcion = forms.CharField(
        validators=[validate_safe_text],
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    class Meta:
        model = Incidencia
        fields = ["cuadrilla", "trabajador", "tipo", "descripcion"]

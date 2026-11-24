from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta

from .validators import validate_no_malicious_content, validate_safe_text

class Proyecto(models.Model):
    MAX_PRESUPUESTO = Decimal("1000000000.00")
    MIN_DURACION = timedelta(weeks=3)
    ESTADO_CHOICES = [
        ('planificado', 'Planificado'),
        ('en_progreso', 'En progreso'),
        ('completado', 'Completado'),
        ('cancelado', 'Cancelado'),
    ]

    codigo = models.AutoField(primary_key=True)
    nombre = models.CharField("Nombre del proyecto", max_length=100, unique=True)
    cliente = models.CharField("Cliente", max_length=100)
    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default='planificado')
    fecha_inicio = models.DateField("Fecha de inicio", default=timezone.localdate)
    fecha_termino = models.DateField("Fecha de término", null=True, blank=True)
    presupuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(MAX_PRESUPUESTO),
        ],
    )
    direccion = models.CharField("Dirección", max_length=255)
    ciudad = models.CharField("Ciudad", max_length=100)
    descripcion = models.TextField("Descripción", blank=True)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='unique_proyecto_nombre'),
            # Defensa en la base de datos: aunque una vista olvide validar, no se
            # guarda un presupuesto fuera de rango.
            models.CheckConstraint(
                condition=models.Q(presupuesto__gte=0) & models.Q(presupuesto__lte=Decimal("1000000000.00")),
                name='proyecto_presupuesto_rango',
            ),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        hoy = timezone.localdate()
        if self.fecha_inicio and self.fecha_inicio < hoy:
            raise ValidationError(
                "La fecha de inicio del proyecto no puede ser anterior a hoy."
            )
        if self.fecha_termino:
            if self.fecha_termino < hoy:
                raise ValidationError(
                    "La fecha de término del proyecto no puede ser anterior a hoy."
                )
            if self.fecha_inicio and self.fecha_termino < self.fecha_inicio:
                raise ValidationError(
                    "La fecha de término no puede ser anterior a la fecha de inicio."
                )
            if (
                self.fecha_inicio
                and self.fecha_termino - self.fecha_inicio < self.MIN_DURACION
            ):
                raise ValidationError(
                    "El proyecto debe durar como mínimo 3 semanas."
                )


class Cuadrilla(models.Model):
    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('en_asignacion', 'En proceso de asignación'),
        ('asignada', 'Asignada'),
    ]

    nombre = models.CharField("Nombre de la cuadrilla", max_length=100)
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="cuadrillas",  
        verbose_name="Proyecto asignado"
    )
    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default='disponible')
    trabajador = models.ForeignKey(
        'Integrante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cuadrillas_lideradas",
        verbose_name="Líder de cuadrilla",
        limit_choices_to={'cargo': 'lider'}
    )
    jornada_inicio = models.DateTimeField("Inicio de jornada", null=True, blank=True)
    jornada_fin = models.DateTimeField("Fin de jornada", null=True, blank=True)
    fecha_inicio_jornada = models.DateField("Primer día de jornada", null=True, blank=True)
    fecha_fin_jornada = models.DateField("Último día de jornada", null=True, blank=True)
    horas_diarias = models.DecimalField(
        "Horas diarias",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("8"))],
    )
    tamanio_aprobado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cuadrillas_aprobadas",
        verbose_name="Tamaño aprobado por",
    )
    fecha_aprobacion_tamanio = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cuadrilla"
        verbose_name_plural = "Cuadrillas"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='unique_cuadrilla_nombre'),
            models.CheckConstraint(
                condition=models.Q(horas_diarias__isnull=True)
                | (models.Q(horas_diarias__gte=1) & models.Q(horas_diarias__lte=8)),
                name='cuadrilla_horas_diarias_rango',
            ),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        if self.pk and not 3 <= self.integrantes.count() <= 5:
            raise ValidationError("La cuadrilla debe tener entre 3 y 5 trabajadores.")
        if self.pk:
            roles = list(
                self.integrantes.filter(cargo__in=("lider", "supervisor"))
                .values_list("cargo", flat=True)
            )
            if roles.count("lider") > 1:
                raise ValidationError(
                    "Una cuadrilla no puede tener más de un líder de cuadrilla."
                )
            if roles.count("supervisor") > 1:
                raise ValidationError(
                    "Una cuadrilla no puede tener más de un jefe de obra."
                )
        if self.jornada_inicio and self.jornada_fin:
            ahora = timezone.now()
            if self.jornada_inicio < ahora or self.jornada_fin < ahora:
                raise ValidationError(
                    "Las fechas de jornada no pueden ser anteriores a ahora."
                )
            if self.jornada_fin <= self.jornada_inicio:
                raise ValidationError("La jornada debe finalizar después de su inicio.")
            if self.jornada_fin - self.jornada_inicio > timedelta(hours=24):
                raise ValidationError("Una cuadrilla no puede trabajar más de 24 horas seguidas.")
        if self.fecha_inicio_jornada or self.fecha_fin_jornada or self.horas_diarias is not None:
            if not self.fecha_inicio_jornada or not self.fecha_fin_jornada or self.horas_diarias is None:
                raise ValidationError("Debe indicar ambos días y la cantidad de horas diarias.")
            if self.fecha_inicio_jornada < timezone.localdate():
                raise ValidationError("El primer día de jornada no puede ser anterior a hoy.")
            if self.fecha_fin_jornada < timezone.localdate():
                raise ValidationError("El último día de jornada no puede ser anterior a hoy.")
            if self.fecha_fin_jornada < self.fecha_inicio_jornada:
                raise ValidationError("El último día no puede ser anterior al primer día.")
            if not Decimal("1") <= self.horas_diarias <= Decimal("8"):
                raise ValidationError("Las horas diarias deben estar entre 1 y 8.")

    @property
    def cantidad_integrantes(self):
        return self.integrantes.count()

    @property
    def requiere_aprobacion_tamanio(self):
        return not 3 <= self.cantidad_integrantes <= 5

class Integrante(models.Model):
    CARGO_CHOICES = [
        ('operario', 'Operario'),
        ('ayudante', 'Ayudante'),
        ('supervisor', 'Supervisor'),
        ('lider', 'Líder de cuadrilla'),
    ]
    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('asignado', 'Asignado'),
        ('licencia', 'En licencia'),
        ('suspendido', 'Suspendido'),
    ]

    ESPECIALIDAD_CHOICES = [
        ('electricista', 'Electricista'),
        ('albanil', 'Albañil'),
        ('fontanero', 'Fontanero'),
        ('pintor', 'Pintor'),
        ('carpintero', 'Carpintero'), # Added Carpenter as a common extra
        ('jornal', 'Jornal'), # Added Jornal as a common extra
        ('otro', 'Otro'),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="integrante",
        verbose_name="Usuario",
        null=True,
        blank=True
    )
    nombre_trabajador = models.CharField("Nombre", max_length=100, blank=True)
    apellido_trabajador = models.CharField("Apellido", max_length=100, blank=True)
    cargo = models.CharField("Cargo", max_length=20, choices=CARGO_CHOICES)
    cuadrilla = models.ForeignKey(
        'Cuadrilla',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integrantes"
    )
    especialidad = models.CharField("Especialidad", max_length=20, choices=ESPECIALIDAD_CHOICES, blank=True, null=True)
    estado = models.CharField("Estado del trabajador", max_length=15, choices=ESTADO_CHOICES, default='disponible')
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    notas = models.TextField("Notas internas", blank=True)
    licencia_inicio = models.DateField("Inicio de licencia", null=True, blank=True)
    licencia_fin = models.DateField("Fin de licencia", null=True, blank=True)

    class Meta:
        verbose_name = "Integrante"
        verbose_name_plural = "Integrantes"
        ordering = ["nombre_trabajador", "apellido_trabajador", "usuario__first_name", "usuario__last_name"]

    def get_nombre_completo(self):
        """Retorna el nombre completo del trabajador."""
        if self.usuario:
            return self.usuario.get_full_name() or self.usuario.username
        else:
            return f"{self.nombre_trabajador} {self.apellido_trabajador}".strip() or "Sin nombre"

    @property
    def nombre(self):
        """Retorna el nombre completo del trabajador (compatibilidad)."""
        return self.get_nombre_completo()

    def __str__(self):
        return f"{self.get_nombre_completo()} — {self.get_cargo_display()}"

    def clean(self):
        super().clean()
        if self.cargo == "lider":
            if not self.usuario_id:
                raise ValidationError(
                    "Solo una cuenta con rol Líder de Cuadrilla puede ser líder."
                )
            perfil = getattr(self.usuario, "perfil", None)
            if not perfil or perfil.rol != "lider_cuadrilla":
                raise ValidationError(
                    "La cuenta asociada debe tener el rol Líder de Cuadrilla."
                )
        if not self.cuadrilla_id or self.cargo not in ("lider", "supervisor"):
            return
        if Integrante.objects.filter(
            cuadrilla_id=self.cuadrilla_id,
            cargo=self.cargo,
        ).exclude(pk=self.pk).exists():
            cargo = "líder de cuadrilla" if self.cargo == "lider" else "jefe de obra"
            raise ValidationError(
                f"Una cuadrilla no puede tener más de un {cargo}."
            )


class CambioCuadrilla(models.Model):
    ACCION_CHOICES = [
        ('creacion', 'Creación'),
        ('actualizacion', 'Actualización'),
        ('reasignacion', 'Reasignación'),
        ('estado', 'Cambio de estado'),
        ('eliminacion', 'Eliminación'),
    ]

    cuadrilla = models.ForeignKey(Cuadrilla, on_delete=models.SET_NULL, null=True, blank=True, related_name="cambios")
    accion = models.CharField("Tipo de acción", max_length=20, choices=ACCION_CHOICES)
    descripcion = models.TextField("Detalle del cambio")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cambio de cuadrilla"
        verbose_name_plural = "Cambios de cuadrilla"
        ordering = ["-fecha"]

    def __str__(self):
        if self.cuadrilla:
            return f"{self.get_accion_display()} · {self.cuadrilla.nombre} ({self.fecha:%d/%m %H:%M})"
        else:
            return f"{self.get_accion_display()} · [Cuadrilla eliminada] ({self.fecha:%d/%m %H:%M})"


class SolicitudReasignacion(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]

    trabajador = models.ForeignKey(
        Integrante,
        on_delete=models.CASCADE,
        related_name="solicitudes_reasignacion",
        verbose_name="Trabajador"
    )
    cuadrilla_origen = models.ForeignKey(
        Cuadrilla,
        on_delete=models.CASCADE,
        related_name="solicitudes_salida",
        verbose_name="Cuadrilla origen"
    )
    cuadrilla_destino = models.ForeignKey(
        Cuadrilla,
        on_delete=models.CASCADE,
        related_name="solicitudes_entrada",
        verbose_name="Cuadrilla destino"
    )
    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    motivo = models.TextField("Motivo de la solicitud", blank=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_respondidas",
        verbose_name="Respondido por"
    )

    class Meta:
        verbose_name = "Solicitud de Reasignación"
        verbose_name_plural = "Solicitudes de Reasignación"
        ordering = ["-fecha_solicitud"]

    def __str__(self):
        return f"Solicitud de {self.trabajador.get_nombre_completo()} - {self.get_estado_display()}"


class Incidencia(models.Model):
    TIPO_CHOICES = [
        ("ausencia", "Ausencia de trabajador"),
        ("accidente", "Accidente"),
        ("atraso", "Atraso"),
        ("otro", "Otra incidencia"),
    ]

    cuadrilla = models.ForeignKey(Cuadrilla, on_delete=models.CASCADE, related_name="incidencias")
    trabajador = models.ForeignKey(
        Integrante,
        on_delete=models.CASCADE,
        related_name="incidencias",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="incidencias_registradas")
    notificado = models.BooleanField(default=False)
    fecha_notificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha"]

    def clean(self):
        super().clean()
        # Defensa en profundidad: aunque una vista olvide validar, el modelo no
        # acepta descripciones largas ni con código/enlaces (se reenvían por correo).
        maximo = getattr(settings, "INCIDENT_DESCRIPTION_MAX_LENGTH", 500)
        if len(self.descripcion or "") > maximo:
            raise ValidationError(f"La descripción no puede superar {maximo} caracteres.")
        validate_safe_text(self.descripcion)
        validate_no_malicious_content(self.descripcion)
        if self.trabajador_id and self.trabajador.cuadrilla_id != self.cuadrilla_id:
            raise ValidationError("El trabajador debe pertenecer a la cuadrilla de la incidencia.")

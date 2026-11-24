import logging
from datetime import datetime, timedelta

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProyectoForm
from .models import (
    CambioCuadrilla,
    Cuadrilla,
    Incidencia,
    Integrante,
    Proyecto,
    SolicitudReasignacion,
)
from .permissions import is_jefe_obra
from .request_validation import (
    clean_text,
    excel_safe,
    parse_aware_datetime,
    parse_choice,
    parse_date,
    parse_decimal,
    parse_id_list,
    parse_int_id,
)
from .services import DashboardStatsService
from .sync import ensure_fresh
from .validators import (
    validate_form_input_lengths,
    validate_no_malicious_content,
    validate_person_name,
    validate_plain_text,
    validate_safe_text,
)

logger = logging.getLogger(__name__)

MIN_INTEGRANTES = 3
MAX_INTEGRANTES = 5
MSG_TAMANIO = "La cuadrilla debe tener un mínimo de 3 y un máximo de 5 trabajadores."

# Códigos de error de Django para los que conviene anteponer el nombre del campo
# ("Presupuesto: Introduzca un número."), porque el mensaje por sí solo no lo dice.
_CODIGOS_GENERICOS = {
    "required", "invalid", "max_length", "min_value", "max_value", "max_digits",
    "max_decimal_places", "max_whole_digits", "invalid_choice", "null", "blank",
}


# ======================
# UTILIDADES COMUNES
# ======================
def _fail(request, message, route, **route_kwargs):
    """Muestra el error y redirige. Nunca deja que un dato inválido llegue a la BD."""
    messages.error(request, message)
    return redirect(route, **route_kwargs)


def _first_form_error(form):
    for field, errors in form.errors.as_data().items():
        error = errors[0]
        message = error.messages[0]
        if field != NON_FIELD_ERRORS and error.code in _CODIGOS_GENERICOS and field in form.fields:
            return f"{form.fields[field].label or field}: {message}"
        return message
    return "Los datos enviados no son válidos."


def _validate_post_input_lengths(request, redirect_name, *, limits=None, **redirect_kwargs):
    try:
        validate_form_input_lengths(request.POST, limits=limits)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect(redirect_name, **redirect_kwargs)
    return None


def _sync_o_redirigir(request, route, **route_kwargs):
    """
    Rechaza el guardado si la pantalla quedó desactualizada porque otro equipo
    modificó datos mientras tanto (ver core/sync.py). Devuelve una respuesta o None.
    """
    try:
        ensure_fresh(request)
    except ValidationError as error:
        return _fail(request, error.messages[0], route, **route_kwargs)
    return None


def _es_lider_de(user, cuadrilla):
    """True si ``user`` es la cuenta del líder de esa cuadrilla (None-safe: una cuadrilla puede no tener líder)."""
    lider = cuadrilla.trabajador
    return lider is not None and lider.usuario_id == user.id


def _puede_gestionar_cuadrilla(user, cuadrilla):
    return is_jefe_obra(user) or _es_lider_de(user, cuadrilla)


def registrar_cambio(cuadrilla, accion, descripcion):
    """Helper centralizado para registrar cualquier alteración a las cuadrillas."""
    if not cuadrilla:
        return
    CambioCuadrilla.objects.create(
        cuadrilla=cuadrilla,
        accion=accion,
        descripcion=descripcion.strip(),
    )


def _validar_cupo(cuadrilla, cargo, excluir_pk=None):
    """Tamaño máximo (5) y unicidad de líder / jefe de obra al ingresar alguien a ``cuadrilla``."""
    miembros = cuadrilla.integrantes.all()
    if excluir_pk:
        miembros = miembros.exclude(pk=excluir_pk)
    if miembros.count() >= MAX_INTEGRANTES:
        raise ValidationError(f"La cuadrilla {cuadrilla.nombre} ya tiene el máximo de {MAX_INTEGRANTES} trabajadores.")
    if cargo in ("lider", "supervisor") and miembros.filter(cargo=cargo).exists():
        nombre_cargo = "líder de cuadrilla" if cargo == "lider" else "jefe de obra"
        raise ValidationError(f"Una cuadrilla no puede tener más de un {nombre_cargo}.")


@transaction.atomic
def _mover_integrante(integrante_id, destino_id):
    """
    Traslada a un trabajador validando estado, cupo y roles bajo bloqueo de filas.
    Devuelve la cuadrilla de origen. Lanza ValidationError si no corresponde.
    """
    destino = Cuadrilla.objects.select_for_update().get(pk=destino_id)
    integrante = Integrante.objects.select_for_update().get(pk=integrante_id)
    if integrante.estado in ("licencia", "suspendido"):
        raise ValidationError(
            f"{integrante.get_nombre_completo()} no puede ser asignado porque está en estado "
            f"«{integrante.get_estado_display()}»."
        )
    _validar_cupo(destino, integrante.cargo, excluir_pk=integrante.pk)
    origen = integrante.cuadrilla
    integrante.cuadrilla = destino
    integrante.estado = "asignado"
    integrante.save()
    return origen


# ======================
# PÁGINA PRINCIPAL
# ======================
@login_required
def index(request):
    dashboard_service = DashboardStatsService()
    context = dashboard_service.get_dashboard_context()
    return render(request, "core/index.html", context)


# ======================
# PROYECTO
# ======================
@login_required
def proyecto_view(request):
    if request.method == "POST":
        if not is_jefe_obra(request.user):
            messages.error(request, "Solo el Jefe de Obra puede crear proyectos.")
            return redirect("index")
        length_error = _validate_post_input_lengths(request, "proyecto")
        if length_error:
            return length_error

        # Se valida con ProyectoForm: tipos, opciones de 'estado', rangos, fechas,
        # nombre único y validadores de texto, igual que cualquier formulario Django.
        data = request.POST.copy()
        if not data.get("fecha_inicio"):
            data["fecha_inicio"] = timezone.localdate().isoformat()
        if not data.get("estado"):
            data["estado"] = "planificado"
        form = ProyectoForm(data)
        if not form.is_valid():
            return _fail(request, _first_form_error(form), "proyecto")
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:  # dos peticiones simultáneas con el mismo nombre
            return _fail(request, "Ya existe un proyecto con ese nombre. Elija otro nombre.", "proyecto")
        messages.success(request, "✅ Proyecto registrado correctamente.")
        return redirect("proyecto")

    proyectos = Proyecto.objects.all()
    return render(request, "core/proyecto.html", {"proyectos": proyectos})


@login_required
@require_POST
def eliminar_proyecto(request, codigo):
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede eliminar proyectos.")
        return redirect("proyecto")
    proyecto = get_object_or_404(Proyecto, codigo=codigo)
    proyecto.delete()
    list(get_messages(request))
    messages.success(request, "Proyecto eliminado correctamente.")
    return redirect("proyecto")


@login_required
def editar_proyecto(request, codigo):
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede editar proyectos.")
        return redirect("proyecto")
    proyecto = get_object_or_404(Proyecto, codigo=codigo)

    if request.method == "POST":
        length_error = _validate_post_input_lengths(request, "editar_proyecto", codigo=codigo)
        if length_error:
            return length_error

        data = request.POST.copy()
        # Campos omitidos conservan su valor actual (comportamiento previo).
        if not data.get("estado"):
            data["estado"] = proyecto.estado
        if not data.get("fecha_inicio"):
            data["fecha_inicio"] = proyecto.fecha_inicio.isoformat()
        if not data.get("presupuesto"):
            data["presupuesto"] = str(proyecto.presupuesto)
        form = ProyectoForm(data, instance=proyecto)
        if not form.is_valid():
            return _fail(request, _first_form_error(form), "editar_proyecto", codigo=codigo)
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            return _fail(request, "Ya existe otro proyecto con ese nombre.", "editar_proyecto", codigo=codigo)
        messages.success(request, "Proyecto actualizado correctamente.")
        return redirect("proyecto")

    context = {
        "proyecto": proyecto,
        "estados": Proyecto.ESTADO_CHOICES,
    }
    return render(request, "core/editar_proyecto.html", context)


# ======================
# CUADRILLA — lectura y validación de datos
# ======================
class _IrAAgregarTrabajador(Exception):
    """El formulario trae datos de trabajadores nuevos: se deriva a la vista dedicada."""


def _leer_jornada(request, es_nueva):
    """Devuelve (jornada_inicio, jornada_fin, fecha_inicio, fecha_fin, horas_diarias) validados."""
    ahora = timezone.now()
    hoy = timezone.localdate()

    inicio_raw = request.POST.get("jornada_inicio") or None
    fin_raw = request.POST.get("jornada_fin") or None
    jornada_inicio = jornada_fin = None
    if inicio_raw or fin_raw:
        jornada_inicio = parse_aware_datetime(inicio_raw, "la fecha de inicio de la jornada")
        jornada_fin = parse_aware_datetime(fin_raw, "la fecha de fin de la jornada")
        if jornada_inicio < ahora or jornada_fin < ahora:
            raise ValidationError("Las fechas de jornada no pueden ser anteriores a ahora.")
        if jornada_fin <= jornada_inicio or jornada_fin - jornada_inicio > timedelta(hours=24):
            raise ValidationError("La jornada debe durar más de 0 y como máximo 24 horas.")

    fi_raw = request.POST.get("fecha_inicio_jornada") or None
    ff_raw = request.POST.get("fecha_fin_jornada") or None
    horas_raw = request.POST.get("horas_diarias") or None
    fecha_inicio = fecha_fin = horas = None
    if es_nueva and not all((fi_raw, ff_raw, horas_raw)):
        raise ValidationError("Al crear una cuadrilla debe indicar los días y las horas diarias.")
    if any((fi_raw, ff_raw, horas_raw)):
        if not all((fi_raw, ff_raw, horas_raw)):
            raise ValidationError("Debe indicar el primer día, el último día y las horas diarias.")
        fecha_inicio = parse_date(fi_raw, "el primer día de jornada")
        fecha_fin = parse_date(ff_raw, "el último día de jornada")
        horas = parse_decimal(
            horas_raw, "las horas diarias", min_value=1, max_value=8, decimal_places=2,
            range_message="Las horas diarias deben estar entre 1 y 8.",
        )
        if fecha_inicio < hoy:
            raise ValidationError("El primer día de jornada no puede ser anterior a hoy.")
        if fecha_fin < fecha_inicio:
            raise ValidationError("El último día no puede ser anterior al primer día.")
    return jornada_inicio, jornada_fin, fecha_inicio, fecha_fin, horas


def _resolver_estado(request, integrante):
    """Estado final del trabajador y, si corresponde, su rango de licencia (todo validado)."""
    nombre = integrante.get_nombre_completo()
    estado = parse_choice(
        request.POST.get(f"estado_{integrante.pk}"), Integrante.ESTADO_CHOICES,
        f"El estado de {nombre}", default=integrante.estado,
    )
    if estado != "licencia":
        return ("asignado" if estado == "disponible" else estado), None, None

    user = integrante.usuario
    if user and ((user.first_name == "Felipe" and user.last_name == "Chamorro") or nombre == "Felipe Chamorro"):
        raise ValidationError(f"El usuario {nombre} no puede ser puesto en licencia.")

    inicio_raw = request.POST.get(f"licencia_inicio_{integrante.pk}")
    fin_raw = request.POST.get(f"licencia_fin_{integrante.pk}")
    if (not inicio_raw and not fin_raw and integrante.estado == "licencia"
            and integrante.licencia_inicio and integrante.licencia_fin):
        return "licencia", integrante.licencia_inicio, integrante.licencia_fin
    # Antes solo se exigían fechas a trabajadores con usuario: sin cuenta se podía
    # dejar a alguien "en licencia" sin rango alguno.
    if not inicio_raw or not fin_raw:
        raise ValidationError(f"Debe indicar rango de fecha de licencia para {nombre}.")
    inicio = parse_date(inicio_raw, f"la fecha de inicio de la licencia de {nombre}")
    fin = parse_date(fin_raw, f"la fecha de fin de la licencia de {nombre}")
    if inicio < timezone.localdate():
        raise ValidationError("La fecha de inicio de la licencia debe ser a partir de la fecha actual.")
    if fin < inicio:
        raise ValidationError("La fecha de fin de la licencia no puede ser anterior a la fecha de inicio.")
    return "licencia", inicio, fin


def _preparar_integrantes(request, ids, cuadrilla_actual=None):
    """
    Valida TODO lo relativo a los integrantes enviados (existencia, disponibilidad,
    rol, estado, licencias) sin escribir nada. Devuelve [(integrante, rol, estado, lic_ini, lic_fin)].
    """
    integrantes = {
        i.pk: i for i in Integrante.objects.select_related("usuario").filter(pk__in=ids)
    }
    if len(integrantes) != len(ids):
        raise ValidationError("Alguno de los trabajadores seleccionados no existe.")

    payload = []
    for pk in ids:
        integrante = integrantes[pk]
        nombre = integrante.get_nombre_completo()
        ya_en_cuadrilla = cuadrilla_actual is not None and integrante.cuadrilla_id == cuadrilla_actual.pk
        if integrante.cuadrilla_id and not ya_en_cuadrilla:
            raise ValidationError(f"{nombre} ya está asignado a otra cuadrilla.")
        if not ya_en_cuadrilla and integrante.estado == "licencia":
            raise ValidationError(f"No se puede seleccionar a {nombre} porque está en licencia.")
        if not ya_en_cuadrilla and integrante.estado == "suspendido":
            raise ValidationError(f"No se puede seleccionar a {nombre} porque está suspendido.")

        perfil = getattr(integrante.usuario, "perfil", None)
        rol = parse_choice(
            request.POST.get(f"rol_{pk}"), Integrante.CARGO_CHOICES,
            f"El rol seleccionado para {nombre}", default=integrante.cargo,
        )
        if perfil and perfil.rol == "lider_cuadrilla":
            rol = "lider"
        if rol == "lider" and not (perfil and perfil.rol == "lider_cuadrilla"):
            raise ValidationError(
                f"{nombre} no puede ser líder: debe tener una cuenta registrada como Líder de Cuadrilla."
            )
        estado, lic_ini, lic_fin = _resolver_estado(request, integrante)
        payload.append((integrante, rol, estado, lic_ini, lic_fin))

    if sum(rol == "lider" for _, rol, *_ in payload) > 1:
        raise ValidationError("Solo se permite un líder de cuadrilla por cuadrilla.")
    if sum(rol == "supervisor" for _, rol, *_ in payload) > 1:
        raise ValidationError("Solo se permite un jefe de obra por cuadrilla.")
    return payload


def _escribir_integrantes(cuadrilla, payload):
    """Aplica la asignación ya validada. Debe llamarse dentro de transaction.atomic()."""
    seleccionados = {item[0].pk for item in payload}
    for integrante in cuadrilla.integrantes.select_for_update():
        if integrante.pk not in seleccionados:
            integrante.cuadrilla = None
            if integrante.estado == "asignado":
                integrante.estado = "disponible"
            integrante.save()

    resumen, lider = [], None
    for integrante, rol, estado, lic_ini, lic_fin in payload:
        actual = Integrante.objects.select_for_update().get(pk=integrante.pk)
        # Revalidación bajo bloqueo: otra petición pudo asignarlo mientras tanto.
        if actual.cuadrilla_id and actual.cuadrilla_id != cuadrilla.pk:
            raise ValidationError(f"{actual.get_nombre_completo()} ya está asignado a otra cuadrilla.")
        if estado == "licencia":
            actual.licencia_inicio, actual.licencia_fin = lic_ini, lic_fin
        actual.cargo, actual.estado, actual.cuadrilla = rol, estado, cuadrilla
        actual.save()
        resumen.append(f"{actual.nombre} ({actual.get_cargo_display()} · {actual.get_estado_display()})")
        if rol == "lider":
            lider = actual

    if lider:
        otra = Cuadrilla.objects.select_for_update().filter(
            trabajador=lider, estado__in=("en_asignacion", "asignada"),
        ).exclude(pk=cuadrilla.pk).first()
        if otra:
            raise ValidationError(f"El líder {lider.get_nombre_completo()} ya lidera {otra.nombre}.")
        cuadrilla.trabajador = lider
        cuadrilla.estado = "asignada"
        cuadrilla.save()
    return resumen


def _obtener_proyecto(raw):
    if not str(raw or "").strip():
        raise ValidationError("Debe seleccionar un proyecto.")
    proyecto = Proyecto.objects.filter(pk=parse_int_id(raw, "El proyecto")).first()
    if proyecto is None:
        raise ValidationError("El proyecto seleccionado no existe.")
    return proyecto


def _guardar_cuadrilla(request):
    """
    Crea o actualiza una cuadrilla. Todo se valida antes de escribir y la escritura
    ocurre en una única transacción: ante cualquier error se revierte por completo
    (antes, un `return redirect` dentro del atomic confirmaba cambios a medias).
    Devuelve True si se creó, False si se actualizó.
    """
    nombre = clean_text(
        request.POST.get("nombre"), "el nombre de la cuadrilla",
        required=True, max_length=100, validators=(validate_plain_text,),
    )
    proyecto = _obtener_proyecto(request.POST.get("proyecto"))
    estado = parse_choice(
        request.POST.get("estado"), Cuadrilla.ESTADO_CHOICES, "El estado de la cuadrilla", default="disponible",
    )

    existente_id = None
    if request.POST.get("cuadrilla_id"):
        existente_id = parse_int_id(request.POST.get("cuadrilla_id"), "La cuadrilla")
        if not Cuadrilla.objects.filter(pk=existente_id).exists():
            raise ValidationError("La cuadrilla que intenta editar no existe.")

    duplicadas = Cuadrilla.objects.filter(nombre__iexact=nombre)
    if existente_id:
        duplicadas = duplicadas.exclude(pk=existente_id)
    if duplicadas.exists():
        raise ValidationError("Ya existe una cuadrilla con ese nombre. Elija otro nombre.")

    nuevos_presentes = any(
        x.strip() for x in (
            request.POST.getlist("nombre_trabajador_nuevo")
            + request.POST.getlist("apellido_trabajador_nuevo")
            + request.POST.getlist("cargo_trabajador_nuevo")
        )
    )
    ids = parse_id_list(
        request.POST.getlist("integrantes"), "Los trabajadores seleccionados",
        max_items=MAX_INTEGRANTES, too_many_message=MSG_TAMANIO,
    )
    if not ids and not nuevos_presentes:
        raise ValidationError("Debe seleccionar al menos un integrante o crear un trabajador nuevo.")
    if nuevos_presentes:
        raise _IrAAgregarTrabajador()
    if not MIN_INTEGRANTES <= len(ids) <= MAX_INTEGRANTES:
        raise ValidationError(MSG_TAMANIO)

    jornada_inicio, jornada_fin, fecha_inicio, fecha_fin, horas = _leer_jornada(request, es_nueva=not existente_id)
    actual_para_validar = Cuadrilla.objects.filter(pk=existente_id).first() if existente_id else None
    payload = _preparar_integrantes(request, ids, actual_para_validar)

    crear = existente_id is None
    with transaction.atomic():
        cuadrilla = Cuadrilla() if crear else Cuadrilla.objects.select_for_update().get(pk=existente_id)
        # Con la fila bloqueada se vuelve a comprobar: si otro equipo guardó entre la primera
        # comprobación y este punto, se aborta y se revierte en vez de pisar sus cambios.
        ensure_fresh(request)
        cuadrilla.nombre = nombre
        cuadrilla.proyecto = proyecto
        cuadrilla.estado = estado
        cuadrilla.jornada_inicio = jornada_inicio
        cuadrilla.jornada_fin = jornada_fin
        cuadrilla.fecha_inicio_jornada = fecha_inicio
        cuadrilla.fecha_fin_jornada = fecha_fin
        cuadrilla.horas_diarias = horas
        cuadrilla.save()

        resumen = _escribir_integrantes(cuadrilla, payload)
        # Última barrera: las reglas del modelo (3-5 integrantes, un líder, un jefe,
        # fechas, horas, unicidad). Si falla, se revierte todo el bloque.
        cuadrilla.full_clean()

        descripcion = f"Cuadrilla {'creada' if crear else 'actualizada'}: {nombre}. "
        descripcion += "Integrantes: " + ", ".join(resumen)
        registrar_cambio(cuadrilla, "creacion" if crear else "actualizacion", descripcion)
    return crear


def _reubicar_integrante(request):
    if not request.POST.get("integrante_id") or not request.POST.get("cuadrilla_destino"):
        raise ValidationError("Debe seleccionar el trabajador y la cuadrilla destino.")
    integrante = get_object_or_404(Integrante, pk=parse_int_id(request.POST.get("integrante_id"), "El trabajador"))
    destino = get_object_or_404(Cuadrilla, pk=parse_int_id(request.POST.get("cuadrilla_destino"), "La cuadrilla destino"))
    if integrante.cuadrilla_id == destino.pk:
        return "info"
    origen = _mover_integrante(integrante.pk, destino.pk)
    descripcion = f"{integrante.nombre} fue reasignado"
    if origen:
        descripcion += f" desde {origen.nombre}"
    descripcion += f" a {destino.nombre}."
    registrar_cambio(destino, "reasignacion", descripcion)
    return "ok"


# ======================
# CUADRILLA
# ======================
@login_required
def cuadrilla_view(request):
    proyectos = Proyecto.objects.all()
    cuadrillas = Cuadrilla.objects.select_related("proyecto", "trabajador").prefetch_related("integrantes").all()
    if not is_jefe_obra(request.user):
        cuadrillas = cuadrillas.filter(trabajador__usuario=request.user)
    historial = CambioCuadrilla.objects.select_related("cuadrilla").order_by("-fecha")[:5]

    cuadrilla = None  # Para edición en el mismo form
    integrantes_qs = Integrante.objects.select_related("cuadrilla", "usuario").order_by(
        "nombre_trabajador", "apellido_trabajador", "usuario__first_name", "usuario__last_name"
    )
    integrantes_form = integrantes_qs.filter(cuadrilla__isnull=True)
    integrantes_cuadrilla_ids = set()
    integrantes_reubicables = integrantes_qs.filter(cuadrilla__isnull=False)

    if request.method == "POST":
        # La autorización va primero: un no-jefe no debe llegar a ninguna otra validación.
        if not is_jefe_obra(request.user):
            messages.error(request, "El Líder de Cuadrilla no puede crear ni modificar asignaciones.")
            return redirect("cuadrilla")
        length_error = _validate_post_input_lengths(request, "cuadrilla")
        if length_error:
            return length_error

        editar_id = request.POST.get("editar_cuadrilla")
        if editar_id:
            try:
                editar_pk = parse_int_id(editar_id, "La cuadrilla")
            except ValidationError as error:
                return _fail(request, error.messages[0], "cuadrilla")
            cuadrilla = get_object_or_404(Cuadrilla, id=editar_pk)
            integrantes_form = integrantes_qs.filter(Q(cuadrilla__isnull=True) | Q(cuadrilla=cuadrilla))
            integrantes_cuadrilla_ids = set(cuadrilla.integrantes.values_list("id", flat=True))
        else:
            try:
                ensure_fresh(request)
                if request.POST.get("accion", "guardar") == "reubicar":
                    resultado = _reubicar_integrante(request)
                    if resultado == "info":
                        messages.info(request, "El trabajador ya pertenece a la cuadrilla seleccionada.")
                    else:
                        messages.success(request, "Trabajador reasignado correctamente.")
                    return redirect("cuadrilla")
                crear = _guardar_cuadrilla(request)
            except _IrAAgregarTrabajador:
                messages.info(request, "Para agregar trabajadores sin usuario, use la página 'Agregar Trabajador'.")
                return redirect("agregar_trabajador")
            except ValidationError as error:
                return _fail(request, error.messages[0], "cuadrilla")
            except IntegrityError:
                return _fail(request, "No se pudo guardar: ya existe una cuadrilla con ese nombre.", "cuadrilla")
            messages.success(
                request,
                "✅ Cuadrilla registrada correctamente." if crear else "Cuadrilla actualizada correctamente.",
            )
            return redirect("cuadrilla")

    if cuadrilla and not integrantes_cuadrilla_ids:
        integrantes_cuadrilla_ids = set(cuadrilla.integrantes.values_list("id", flat=True))
    if cuadrilla:
        integrantes_form = integrantes_qs.filter(Q(cuadrilla__isnull=True) | Q(cuadrilla=cuadrilla))

    return render(request, "core/cuadrilla.html", {
        "proyectos": proyectos,
        "integrantes_form": integrantes_form,
        "integrantes_reubicables": integrantes_reubicables,
        "integrantes_cuadrilla_ids": integrantes_cuadrilla_ids,
        "cuadrillas": cuadrillas,
        "cuadrilla": cuadrilla,
        "historial": historial,
        "cargo_choices": Integrante.CARGO_CHOICES,
        "estado_choices": Integrante.ESTADO_CHOICES,
        "hoy": timezone.localdate(),
    })


# ======================
# VER UNA CUADRILLA
# ======================
@login_required
def ver_cuadrilla(request, cuadrilla_id):
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    if not _puede_gestionar_cuadrilla(request.user, cuadrilla):
        messages.error(request, "No puedes consultar una cuadrilla de otra obra.")
        return redirect("index")
    return render(request, "core/ver_cuadrilla.html", {"cuadrilla": cuadrilla})


# ======================
# EDITAR CUADRILLA
# ======================
@login_required
def editar_cuadrilla(request, cuadrilla_id):
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede editar cuadrillas.")
        return redirect("cuadrilla")
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id)
    proyectos = Proyecto.objects.all()
    integrantes_disponibles = Integrante.objects.filter(Q(cuadrilla__isnull=True) | Q(cuadrilla=cuadrilla))

    if request.method == "POST":
        length_error = _validate_post_input_lengths(request, "editar_cuadrilla", cuadrilla_id=cuadrilla_id)
        if length_error:
            return length_error
        try:
            ensure_fresh(request)
            nombre = clean_text(
                request.POST.get("nombre"), "el nombre de la cuadrilla",
                required=True, max_length=100, validators=(validate_plain_text,),
            )
            proyecto = _obtener_proyecto(request.POST.get("proyecto"))
            estado = parse_choice(
                request.POST.get("estado"), Cuadrilla.ESTADO_CHOICES,
                "El estado de la cuadrilla", default=cuadrilla.estado,
            )
            if Cuadrilla.objects.filter(nombre__iexact=nombre).exclude(pk=cuadrilla.pk).exists():
                raise ValidationError("Ya existe una cuadrilla con ese nombre. Elija otro nombre.")
            ids = parse_id_list(
                request.POST.getlist("integrantes"), "Los trabajadores seleccionados",
                max_items=MAX_INTEGRANTES, too_many_message=MSG_TAMANIO,
            )
            if not MIN_INTEGRANTES <= len(ids) <= MAX_INTEGRANTES:
                raise ValidationError(MSG_TAMANIO)
            # Solo se pueden elegir los trabajadores que el formulario ofrece (libres o ya
            # de esta cuadrilla): antes se podía "robar" gente de otras cuadrillas por ID.
            permitidos = set(integrantes_disponibles.filter(pk__in=ids).values_list("pk", flat=True))
            if permitidos != set(ids):
                raise ValidationError("Alguno de los trabajadores seleccionados no está disponible.")
            payload = _preparar_integrantes(request, ids, cuadrilla)

            with transaction.atomic():
                cuadrilla = Cuadrilla.objects.select_for_update().get(pk=cuadrilla.pk)
                ensure_fresh(request)  # bajo bloqueo (ver _guardar_cuadrilla)
                cuadrilla.nombre, cuadrilla.proyecto, cuadrilla.estado = nombre, proyecto, estado
                cuadrilla.save()
                resumen = _escribir_integrantes(cuadrilla, payload)
                cuadrilla.full_clean()
                registrar_cambio(
                    cuadrilla, "actualizacion",
                    f"Cuadrilla actualizada: {nombre}. Integrantes: " + ", ".join(resumen),
                )
        except ValidationError as error:
            return _fail(request, error.messages[0], "editar_cuadrilla", cuadrilla_id=cuadrilla_id)
        except IntegrityError:
            return _fail(request, "No se pudo guardar: ya existe una cuadrilla con ese nombre.",
                         "editar_cuadrilla", cuadrilla_id=cuadrilla_id)
        messages.success(request, "✅ Cuadrilla actualizada correctamente.")
        return redirect("cuadrilla")

    return render(request, "core/cuadrilla_form.html", {
        "cuadrilla": cuadrilla,
        "proyectos": proyectos,
        "integrantes_disponibles": integrantes_disponibles,
    })


@login_required
def agregar_trabajador(request):
    """Vista para agregar un trabajador sin usuario (operario/ayudante/supervisor)."""
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede agregar trabajadores.")
        return redirect("cuadrilla")
    if request.method == "POST":
        length_error = _validate_post_input_lengths(request, "agregar_trabajador")
        if length_error:
            return length_error
        nombre = request.POST.get("nombre_trabajador", "").strip()
        apellido = request.POST.get("apellido_trabajador", "").strip()
        if not nombre or not apellido:
            return _fail(request, "Debe indicar nombre y apellido.", "agregar_trabajador")
        try:
            ensure_fresh(request)
            validate_person_name(nombre)
            validate_person_name(apellido)
            cargo = parse_choice(request.POST.get("cargo"), Integrante.CARGO_CHOICES, "El cargo", default="operario")
            especialidad = parse_choice(
                request.POST.get("especialidad"), Integrante.ESPECIALIDAD_CHOICES, "La especialidad", default="otro",
            )
            if cargo == "lider":
                raise ValidationError("Solo una cuenta registrada como Líder de Cuadrilla puede tener ese cargo.")
            cuadrilla_id = None
            if request.POST.get("cuadrilla"):
                cuadrilla_id = parse_int_id(request.POST.get("cuadrilla"), "La cuadrilla")
                if not Cuadrilla.objects.filter(pk=cuadrilla_id).exists():
                    raise ValidationError("La cuadrilla seleccionada no existe.")

            with transaction.atomic():
                cuadrilla = None
                if cuadrilla_id:
                    cuadrilla = Cuadrilla.objects.select_for_update().get(pk=cuadrilla_id)
                    _validar_cupo(cuadrilla, cargo)
                integrante = Integrante.objects.create(
                    nombre_trabajador=nombre,
                    apellido_trabajador=apellido,
                    cargo=cargo,
                    especialidad=especialidad,
                    cuadrilla=cuadrilla,
                    estado="asignado" if cuadrilla else "disponible",
                )
        except ValidationError as error:
            return _fail(request, error.messages[0], "agregar_trabajador")
        messages.success(request, f"✅ Trabajador {integrante.get_nombre_completo()} creado correctamente.")
        return redirect("cuadrilla")

    proyectos = Proyecto.objects.all()
    cuadrillas = Cuadrilla.objects.all()
    return render(request, "core/trabajador_form.html", {"cuadrillas": cuadrillas, "proyectos": proyectos})


@login_required
@require_POST
def eliminar_integrante(request, integrante_id):
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede eliminar trabajadores.")
        return redirect("cuadrilla")
    integrante = get_object_or_404(Integrante, id=integrante_id)
    if integrante.usuario is not None:
        messages.error(request, "Solo se pueden eliminar trabajadores sin usuario desde esta acción.")
        return redirect("cuadrilla")
    length_error = _validate_post_input_lengths(request, "cuadrilla")
    if length_error:
        return length_error
    sync_error = _sync_o_redirigir(request, "cuadrilla")
    if sync_error:
        return sync_error
    integrante.delete()
    messages.success(request, "✅ Trabajador eliminado correctamente.")
    return redirect("cuadrilla")


# ======================
# ELIMINAR CUADRILLA
# ======================
@login_required
@require_POST
def eliminar_cuadrilla(request, cuadrilla_id):
    if not is_jefe_obra(request.user):
        messages.error(request, "Solo el Jefe de Obra puede eliminar cuadrillas.")
        return redirect("cuadrilla")
    length_error = _validate_post_input_lengths(request, "cuadrilla")
    if length_error:
        return length_error
    sync_error = _sync_o_redirigir(request, "cuadrilla")
    if sync_error:
        return sync_error
    with transaction.atomic():
        cuadrilla = get_object_or_404(Cuadrilla.objects.select_for_update(), id=cuadrilla_id)
        integrantes_cantidad = cuadrilla.integrantes.count()
        lider_nombre = cuadrilla.trabajador.get_nombre_completo() if cuadrilla.trabajador else "Sin líder"
        CambioCuadrilla.objects.create(
            cuadrilla=cuadrilla,
            accion="eliminacion",
            descripcion=(
                f"Cuadrilla eliminada. Líder: {lider_nombre}. "
                f"Integrantes desasignados: {integrantes_cantidad}. Eliminado por: {request.user.username}"
            ),
        )
        for integrante in cuadrilla.integrantes.all():
            integrante.cuadrilla = None
            integrante.save()
        cuadrilla.delete()
    messages.success(request, "✅ Cuadrilla eliminada correctamente y registrada en cambios.")
    return redirect("cuadrilla")


# ======================
# INCIDENCIAS
# ======================
def _limpiar_descripcion_incidencia(raw):
    """Texto simple, de largo y líneas acotados, sin código ni enlaces."""
    maximo = getattr(settings, "INCIDENT_DESCRIPTION_MAX_LENGTH", 500)
    minimo = getattr(settings, "INCIDENT_DESCRIPTION_MIN_LENGTH", 5)
    max_lineas = getattr(settings, "INCIDENT_DESCRIPTION_MAX_LINES", 10)
    texto = clean_text(
        raw, "la descripción", required=True, max_length=maximo,
        validators=(validate_safe_text, validate_no_malicious_content),
    )
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    if len(texto) < minimo:
        raise ValidationError(f"La descripción debe tener al menos {minimo} caracteres.")
    lineas = [linea.strip() for linea in texto.split("\n")]
    if len([linea for linea in lineas if linea]) > max_lineas:
        raise ValidationError(f"La descripción no puede tener más de {max_lineas} líneas.")
    # Evita rellenar el correo con saltos de línea.
    texto = "\n".join(lineas)
    while "\n\n\n" in texto:
        texto = texto.replace("\n\n\n", "\n\n")
    return texto


def _verificar_limite_incidencias(user):
    """Límite por minuto por usuario y global. Debe llamarse dentro de transaction.atomic()."""
    desde = timezone.now() - timedelta(seconds=60)
    reciente = Incidencia.objects.filter(fecha__gte=desde)
    por_usuario = getattr(settings, "INCIDENT_MAX_PER_MINUTE", 3)
    total = getattr(settings, "INCIDENT_MAX_PER_MINUTE_GLOBAL", 15)
    if reciente.filter(registrado_por=user).count() >= por_usuario:
        raise ValidationError(
            f"Has alcanzado el límite de {por_usuario} incidencias por minuto. Espera un momento e inténtalo de nuevo."
        )
    if reciente.count() >= total:
        raise ValidationError("Se están registrando demasiadas incidencias. Inténtalo de nuevo en un minuto.")


def _una_linea(texto):
    """Sin saltos de línea: evita inyección de cabeceras en el asunto del correo."""
    return " ".join(str(texto).split())[:150]

def pagina_no_encontrada(request, exception):
    return render(request, "core/404.html", status=404)


@login_required
def registrar_incidencia(request):
    if request.method != "POST":
        return render(request, "core/incidencia_form.html", {
            "cuadrillas": Cuadrilla.objects.filter(trabajador__usuario=request.user)
            if not is_jefe_obra(request.user) else Cuadrilla.objects.all(),
        })

    max_desc = getattr(settings, "INCIDENT_DESCRIPTION_MAX_LENGTH", 500)
    # Tope por campo antes de procesar nada (el resto de campos conserva el límite general).
    length_error = _validate_post_input_lengths(
        request, "registrar_incidencia", limits={"descripcion": max_desc * 2},
    )
    if length_error:
        return length_error

    try:
        cuadrilla = get_object_or_404(Cuadrilla, id=parse_int_id(request.POST.get("cuadrilla"), "La cuadrilla"))
        if not _puede_gestionar_cuadrilla(request.user, cuadrilla):
            raise ValidationError("Solo puedes registrar incidencias de tu propia cuadrilla.")

        trabajador = None
        if request.POST.get("trabajador"):
            trabajador = get_object_or_404(
                Integrante, id=parse_int_id(request.POST.get("trabajador"), "El trabajador"),
            )
            if trabajador.cuadrilla_id != cuadrilla.id:
                raise ValidationError("El trabajador no pertenece a la cuadrilla seleccionada.")

        tipo = parse_choice(request.POST.get("tipo"), Incidencia.TIPO_CHOICES, "El tipo de incidencia", default="otro")
        descripcion = _limpiar_descripcion_incidencia(request.POST.get("descripcion"))

        # El bloqueo de la fila del usuario serializa sus envíos simultáneos: sin él,
        # 20 peticiones en paralelo podrían pasar todas la comprobación del límite.
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            _verificar_limite_incidencias(request.user)
            incidencia = Incidencia(
                cuadrilla=cuadrilla, trabajador=trabajador, tipo=tipo,
                descripcion=descripcion, registrado_por=request.user,
            )
            incidencia.full_clean()
            incidencia.save()
    except ValidationError as error:
        logger.warning(
            "Incidencia rechazada (usuario=%s, ip=%s): %s",
            request.user.pk, request.META.get("REMOTE_ADDR"), error.messages[0],
        )
        return _fail(request, error.messages[0], "registrar_incidencia")

    destinatarios = []
    if not getattr(settings, "INCIDENT_ONLY_CONFIGURED_EMAILS", False):
        destinatarios = list(
            User.objects.filter(perfil__rol="jefe_obra", email__isnull=False)
            .exclude(email="")
            .values_list("email", flat=True)
        )
    destinatarios.extend(getattr(settings, "INCIDENT_NOTIFICATION_EMAILS", []))
    destinatarios = list(dict.fromkeys(destinatarios))[: getattr(settings, "INCIDENT_MAX_RECIPIENTS", 10)]

    if not destinatarios:
        messages.warning(
            request,
            "La incidencia quedó registrada, pero no hay destinatarios configurados para el correo.",
        )
        return redirect("cuadrilla")
    try:
        mensaje = EmailMessage(
            subject=_una_linea(f"{getattr(settings, 'INCIDENT_EMAIL_SUBJECT_PREFIX', '')} Nueva incidencia en {cuadrilla.nombre}"),
            body=(
                f"Cuadrilla: {cuadrilla.nombre}\n"
                f"Proyecto: {cuadrilla.proyecto.nombre}\n"
                f"Tipo: {incidencia.get_tipo_display()}\n"
                f"Trabajador: {trabajador.get_nombre_completo() if trabajador else 'No especificado'}\n"
                f"Registrada por: {request.user.get_full_name() or request.user.username}\n\n"
                f"{incidencia.descripcion}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=destinatarios,
        )
        # Opciones propias de Mailtrap (Anymail las ignora si se usa otro backend).
        mensaje.esp_extra = {
            "category": "Incidencias",
            "custom_variables": {"incidencia_id": str(incidencia.pk), "tipo": incidencia.tipo},
        }
        enviados = mensaje.send(fail_silently=False)
        if enviados < 1:
            logger.warning(
                "El proveedor no confirmó el correo de la incidencia %s (destinatarios=%s)",
                incidencia.pk,
                len(destinatarios),
            )
            messages.warning(
                request,
                "La incidencia quedó registrada, pero el proveedor no confirmó el envío del correo.",
            )
            return redirect("cuadrilla")
        logger.info(
            "Correo de incidencia enviado (incidencia=%s, destinatarios=%s)",
            incidencia.pk,
            len(destinatarios),
        )
    except Exception:
        # Un fallo SMTP no debe convertir una incidencia ya guardada en un error 500.
        logger.exception("No se pudo enviar el correo de la incidencia %s", incidencia.pk)
        messages.warning(request, "La incidencia quedó registrada, pero no se pudo enviar el correo de aviso.")
        return redirect("cuadrilla")
    incidencia.notificado = True
    incidencia.fecha_notificacion = timezone.now()
    incidencia.save(update_fields=["notificado", "fecha_notificacion"])
    messages.success(request, "Incidencia registrada y notificada al Jefe de Obra.")
    return redirect("cuadrilla")


# ======================
# REASIGNACIONES
# ======================
@login_required
def reasignacion_view(request):
    """Vista para gestionar reasignaciones de trabajadores con sistema de solicitudes."""
    trabajadores = Integrante.objects.select_related("cuadrilla", "usuario").filter(cuadrilla__isnull=False)
    trabajadores_noasignados = Integrante.objects.select_related("usuario").filter(cuadrilla__isnull=True)
    cuadrillas = Cuadrilla.objects.select_related("proyecto").all()
    solicitudes = SolicitudReasignacion.objects.select_related(
        "trabajador", "cuadrilla_origen", "cuadrilla_destino", "respondido_por"
    ).order_by("-fecha_solicitud")[:5]

    user_is_lider = bool(
        request.user.is_authenticated
        and hasattr(request.user, "perfil")
        and request.user.perfil.rol == "lider_cuadrilla"
    )

    if request.method == "POST":
        length_error = _validate_post_input_lengths(request, "reasignacion")
        if length_error:
            return length_error
        accion = request.POST.get("accion")
        try:
            if accion in ("crear_solicitud", "agregar_noasignado", "responder_solicitud"):
                ensure_fresh(request)
            if accion == "crear_solicitud":
                return _crear_solicitud(request)
            if accion == "agregar_noasignado":
                return _agregar_noasignado(request)
            if accion == "responder_solicitud":
                return _responder_solicitud(request)
        except ValidationError as error:
            return _fail(request, error.messages[0], "reasignacion")

    return render(request, "core/reasignacion.html", {
        "trabajadores": trabajadores,
        "cuadrillas": cuadrillas,
        "solicitudes": solicitudes,
        "user_is_lider": user_is_lider,
        "trabajadores_noasignados": trabajadores_noasignados,
    })


def _crear_solicitud(request):
    if not request.POST.get("trabajador_id") or not request.POST.get("cuadrilla_destino"):
        raise ValidationError("Debe seleccionar el trabajador y la cuadrilla destino.")
    motivo = clean_text(request.POST.get("motivo"), "el motivo", max_length=500, validators=(validate_safe_text,))
    trabajador = get_object_or_404(Integrante, id=parse_int_id(request.POST.get("trabajador_id"), "El trabajador"))
    cuadrilla_destino = get_object_or_404(
        Cuadrilla, id=parse_int_id(request.POST.get("cuadrilla_destino"), "La cuadrilla destino"),
    )
    cuadrilla_origen = trabajador.cuadrilla
    if not cuadrilla_origen:
        raise ValidationError("El trabajador no está asignado a ninguna cuadrilla.")
    if not _puede_gestionar_cuadrilla(request.user, cuadrilla_origen):
        raise ValidationError("Solo puedes solicitar cambios desde tu propia cuadrilla.")
    if cuadrilla_origen == cuadrilla_destino:
        messages.info(request, "El trabajador ya pertenece a la cuadrilla seleccionada.")
        return redirect("reasignacion")
    if SolicitudReasignacion.objects.filter(
        trabajador=trabajador, cuadrilla_destino=cuadrilla_destino, estado="pendiente",
    ).exists():
        messages.info(request, "Ya existe una solicitud pendiente para este trabajador y cuadrilla.")
        return redirect("reasignacion")

    SolicitudReasignacion.objects.create(
        trabajador=trabajador,
        cuadrilla_origen=cuadrilla_origen,
        cuadrilla_destino=cuadrilla_destino,
        motivo=motivo,
    )
    messages.success(
        request,
        "✅ Solicitud de reasignación enviada correctamente. Se enviará un correo electrónico con el detalle.",
    )
    return redirect("reasignacion")


def _agregar_noasignado(request):
    if not is_jefe_obra(request.user):
        raise ValidationError("Solo el Jefe de Obra puede asignar trabajadores directamente.")
    if not request.POST.get("trabajador_id") or not request.POST.get("cuadrilla_destino"):
        raise ValidationError("Debe seleccionar el trabajador y la cuadrilla destino.")
    trabajador = get_object_or_404(Integrante, id=parse_int_id(request.POST.get("trabajador_id"), "El trabajador"))
    destino = get_object_or_404(
        Cuadrilla, id=parse_int_id(request.POST.get("cuadrilla_destino"), "La cuadrilla destino"),
    )
    if trabajador.cuadrilla_id is not None:
        raise ValidationError("El trabajador ya está asignado a una cuadrilla.")
    _mover_integrante(trabajador.pk, destino.pk)
    registrar_cambio(
        destino, "agregar_noasignado",
        f"{trabajador.get_nombre_completo()} fue agregado a {destino.nombre} desde estado no asignado.",
    )
    messages.success(request, "✅ Trabajador no asignado agregado correctamente a la cuadrilla.")
    return redirect("reasignacion")


def _responder_solicitud(request):
    if not is_jefe_obra(request.user):
        raise ValidationError("Solo el Jefe de Obra puede aprobar o rechazar reasignaciones.")
    if not request.POST.get("solicitud_id") or not request.POST.get("respuesta"):
        raise ValidationError("Datos inválidos.")
    solicitud_id = parse_int_id(request.POST.get("solicitud_id"), "La solicitud")
    respuesta = parse_choice(request.POST.get("respuesta"), ("aceptar", "rechazar"), "La respuesta")

    with transaction.atomic():
        # Bloqueo de fila: dos clics / dos peticiones simultáneas no pueden aceptar dos veces.
        solicitud = get_object_or_404(SolicitudReasignacion.objects.select_for_update(), id=solicitud_id)
        if solicitud.estado != "pendiente":
            messages.info(request, "Esta solicitud ya fue respondida.")
            return redirect("reasignacion")

        if respuesta == "aceptar":
            trabajador = solicitud.trabajador
            if trabajador.cuadrilla_id != solicitud.cuadrilla_origen_id:
                raise ValidationError(
                    "La solicitud ya no es válida: el trabajador no pertenece a la cuadrilla de origen."
                )
            _mover_integrante(trabajador.pk, solicitud.cuadrilla_destino_id)
            solicitud.estado = "aceptada"
            registrar_cambio(
                solicitud.cuadrilla_destino, "reasignacion",
                f"{trabajador.get_nombre_completo()} fue reasignado desde {solicitud.cuadrilla_origen.nombre} "
                f"a {solicitud.cuadrilla_destino.nombre} (solicitud aceptada).",
            )
            mensaje = ("success", "✅ Solicitud aceptada y trabajador reasignado correctamente.")
        else:
            solicitud.estado = "rechazada"
            mensaje = ("info", "Solicitud rechazada.")
        solicitud.respondido_por = request.user
        solicitud.fecha_respuesta = timezone.now()
        solicitud.save()
    getattr(messages, mensaje[0])(request, mensaje[1])
    return redirect("reasignacion")


@login_required
def historial_cambios_view(request):
    """Vista completa del historial de cambios de cuadrillas."""
    historial = CambioCuadrilla.objects.select_related("cuadrilla").order_by("-fecha")
    return render(request, "core/historial_cambios.html", {
        "historial": historial,
    })


# ======================
# EXPORTAR A EXCEL
# ======================
def _excel_response(df, prefix, sheet_name):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    response["Content-Disposition"] = f'attachment; filename="{prefix}_{timestamp}.xlsx"'
    df.to_excel(response, index=False, sheet_name=sheet_name)
    return response


@login_required
def exportar_excel(request):
    proyectos = Proyecto.objects.all().values(
        "nombre", "cliente", "estado", "fecha_inicio", "fecha_termino",
        "presupuesto", "direccion", "ciudad", "descripcion",
    )
    # excel_safe neutraliza celdas que empiezan con = + - @ (inyección de fórmulas).
    df = pd.DataFrame([{k: excel_safe(v) for k, v in fila.items()} for fila in proyectos])

    if not df.empty:
        for col in ["fecha_inicio", "fecha_termino"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y")

    df.rename(columns={
        "nombre": "Nombre del Proyecto",
        "cliente": "Cliente",
        "estado": "Estado",
        "fecha_inicio": "Fecha de Inicio",
        "fecha_termino": "Fecha de Término",
        "presupuesto": "Presupuesto ($)",
        "direccion": "Dirección",
        "ciudad": "Ciudad",
        "descripcion": "Descripción",
    }, inplace=True)
    df.fillna("—", inplace=True)
    return _excel_response(df, "proyectos", "Proyectos")


@login_required
def exportar_cuadrillas_excel(request):
    cuadrillas = Cuadrilla.objects.select_related("proyecto", "trabajador").all()

    data = []
    for cuadrilla in cuadrillas:
        data.append({
            "nombre": excel_safe(cuadrilla.nombre),
            "proyecto": excel_safe(cuadrilla.proyecto.nombre),
            "estado": cuadrilla.get_estado_display(),
            "lider": excel_safe(cuadrilla.trabajador.get_nombre_completo()) if cuadrilla.trabajador else "Sin líder",
            "integrantes": cuadrilla.integrantes.count(),
        })

    df = pd.DataFrame(data)
    df.rename(columns={
        "nombre": "Nombre de Cuadrilla",
        "proyecto": "Proyecto",
        "estado": "Estado",
        "lider": "Líder",
        "integrantes": "Cantidad de Integrantes",
    }, inplace=True)
    df.fillna("—", inplace=True)
    return _excel_response(df, "cuadrillas", "Cuadrillas")

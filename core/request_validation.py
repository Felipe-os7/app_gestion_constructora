"""
Utilidades para leer y validar datos enviados por el cliente (request.POST).

Principio: nada de lo que llega en una petición es confiable, aunque el HTML
original tenga <select>, min/max o required. Con Burp Suite (o curl) se puede
enviar cualquier cosa, así que el backend debe validar tipo, rango, formato y
pertenencia a las opciones permitidas.

Todas las funciones lanzan ``ValidationError`` con un mensaje listo para
mostrar al usuario (``error.messages[0]``).
"""
import re
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

MAX_DB_INTEGER = 2**63 - 1
MAX_RAW_LENGTH = 64
MIN_YEAR, MAX_YEAR = 2000, 2100

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DECIMAL_RE = re.compile(r"(-?)([0-9]{1,30})(?:\.([0-9]{1,30}))?")


def _as_str(raw):
    return "" if raw is None else str(raw).strip()


def _capitalize(text):
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------- enteros / IDs
def parse_int_id(raw, label="El identificador"):
    """Convierte a entero positivo. Rechaza 'abc', '1e3', '١٢٣', '-1', '' y desbordes."""
    value = _as_str(raw)
    if not (value.isascii() and value.isdigit()) or len(value) > 19:
        raise ValidationError(f"{label} no es válido.")
    number = int(value)
    if not 0 < number <= MAX_DB_INTEGER:
        raise ValidationError(f"{label} no es válido.")
    return number


def parse_id_list(values, label="Los elementos seleccionados", max_items=None, too_many_message=None):
    """Lista de IDs sin duplicados, con tope para evitar inundar la vista de consultas."""
    ids = []
    for raw in values:
        if not _as_str(raw):
            continue
        number = parse_int_id(raw, label)
        if number not in ids:
            ids.append(number)
        if max_items is not None and len(ids) > max_items:
            raise ValidationError(too_many_message or f"{label}: se permiten como máximo {max_items}.")
    return ids


# --------------------------------------------------------------------- opciones
def parse_choice(raw, choices, label, default=None):
    """Valida que el valor esté dentro de ``choices`` (lista de tuplas o de strings)."""
    value = _as_str(raw)
    if not value and default is not None:
        return default
    valid = {c[0] if isinstance(c, (tuple, list)) else c for c in choices}
    if value not in valid:
        raise ValidationError(f"{label} no es válido.")
    return value


# ------------------------------------------------------------------------ texto
def clean_text(raw, label, *, required=False, max_length=None, validators=()):
    """Normaliza (strip), exige/limita largo y aplica validadores. ``label`` en minúscula con artículo."""
    value = _as_str(raw)
    if not value:
        if required:
            raise ValidationError(f"Debe indicar {label}.")
        return ""
    if max_length is not None and len(value) > max_length:
        raise ValidationError(f"{_capitalize(label)} no puede superar {max_length} caracteres.")
    for validator in validators:
        validator(value)
    return value


# ------------------------------------------------------------------------ fechas
def parse_date(raw, label, *, required=False, max_years_ahead=20):
    """Acepta solo AAAA-MM-DD en dígitos ASCII (no '20261112', semanas ISO ni dígitos árabes)."""
    value = _as_str(raw)
    if not value:
        if required:
            raise ValidationError(f"Falta indicar: {label}.")
        return None
    if not _DATE_RE.fullmatch(value):
        raise ValidationError(f"{_capitalize(label)} no tiene un formato válido (use AAAA-MM-DD).")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{_capitalize(label)} no tiene un formato válido (use AAAA-MM-DD).")
    limite = timezone.localdate() + timedelta(days=365 * max_years_ahead)
    if not MIN_YEAR <= parsed.year <= MAX_YEAR or parsed > limite:
        raise ValidationError(f"{_capitalize(label)} está fuera del rango permitido.")
    return parsed


def parse_aware_datetime(raw, label):
    """ISO 8601 -> datetime con zona horaria (evita 'naive vs aware' al comparar con now())."""
    value = _as_str(raw)
    message = f"{_capitalize(label)} no tiene un formato válido."
    if not value or len(value) > 40:
        raise ValidationError(message)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(message)
    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        raise ValidationError(message)
    if timezone.is_naive(parsed):
        try:
            parsed = timezone.make_aware(parsed)
        except (ValueError, OverflowError):
            raise ValidationError(message)
    return parsed


# --------------------------------------------------------------------- decimales
def parse_decimal(raw, label, *, min_value, max_value, decimal_places, range_message=None):
    """
    Decimal finito, sin notación científica y con a lo más ``decimal_places`` decimales.
    Rechaza 'NaN', 'sNaN', 'Infinity', '1e5' (que Decimal() sí acepta y luego rompe
    las comparaciones con InvalidOperation -> error 500).
    """
    value = _as_str(raw)
    invalid = f"{_capitalize(label)} debe ser un número válido."
    if not value or len(value) > MAX_RAW_LENGTH:
        raise ValidationError(invalid)
    match = _DECIMAL_RE.fullmatch(value)
    if not match:
        raise ValidationError(invalid)
    signo, entero, fraccion = match.group(1), match.group(2), (match.group(3) or "").rstrip("0")
    if len(fraccion) > decimal_places:
        raise ValidationError(f"{_capitalize(label)} admite como máximo {decimal_places} decimales.")
    number = Decimal(f"{signo}{entero}.{fraccion}" if fraccion else f"{signo}{entero}")
    if not Decimal(min_value) <= number <= Decimal(max_value):
        raise ValidationError(range_message or f"{_capitalize(label)} está fuera del rango permitido.")
    return number


# ------------------------------------------------------------------------ Excel
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def excel_safe(value):
    """Evita inyección de fórmulas (CSV/Excel injection) en celdas exportadas."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value

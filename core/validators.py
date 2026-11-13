import re
import unicodedata
from collections.abc import Mapping
from django.core.exceptions import ValidationError


MAX_FORM_INPUT_LENGTH = 20
_SQL_INPUT_PATTERN = re.compile(r"(--|/\*|\*/|[;`'\"])", re.IGNORECASE)
# Solo espacio literal entre palabras: "\s" aceptaba saltos de línea y tabulaciones
# ("Obra\n1"), que luego rompen cabeceras de correo, logs y exportaciones.
_PERSON_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?: [^\W\d_]+)*$", re.UNICODE)
_PLAIN_TEXT_PATTERN = re.compile(r"^[^\W_]+(?: [^\W_]+)*$", re.UNICODE)

# Control (Cc), formato invisible/bidi como U+202E o U+200B (Cf), sustitutos (Cs),
# uso privado (Co), no asignados (Cn) y separadores de línea/párrafo (Zl, Zp).
_FORBIDDEN_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}


def validate_safe_text(value):
    """Reject SQL metacharacters and control/invisible characters, preserving normal Spanish text."""
    if value is None:
        return value
    for character in value:
        if character in "\n\r\t":
            continue
        if unicodedata.category(character) in _FORBIDDEN_CATEGORIES:
            raise ValidationError("El texto contiene caracteres de control no permitidos.")
    if _SQL_INPUT_PATTERN.search(value):
        raise ValidationError(
            "El texto contiene caracteres no permitidos. "
            "No se aceptan comillas, punto y coma ni comentarios SQL."
        )
    return value


def validate_form_input_lengths(data, limits=None):
    """
    Reject submitted form values longer than the application limit.

    ``limits`` permite fijar un máximo distinto por campo, p. ej. {"descripcion": 500}.
    """
    if not isinstance(data, Mapping) and not hasattr(data, "lists"):
        return
    limits = limits or {}
    fields = data.lists() if hasattr(data, "lists") else data.items()
    for field_name, values in fields:
        if isinstance(values, str):
            values = [values]
        if field_name == "csrfmiddlewaretoken":
            continue
        limit = limits.get(field_name, MAX_FORM_INPUT_LENGTH)
        if any(len(value) > limit for value in values):
            raise ValidationError(
                f"El campo {field_name} no puede superar "
                f"{limit} caracteres."
            )


def validate_person_name(value):
    if not value or not _PERSON_NAME_PATTERN.fullmatch(value.strip()):
        raise ValidationError(
            "Solo se permiten letras y espacios en el nombre y apellido."
        )
    return value


def validate_plain_text(value):
    if not value or not _PLAIN_TEXT_PATTERN.fullmatch(value.strip()):
        raise ValidationError(
            "Solo se permiten letras, números y espacios; no se permiten caracteres especiales."
        )
    return value

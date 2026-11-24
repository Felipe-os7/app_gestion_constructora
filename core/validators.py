import re
import unicodedata
import urllib.parse
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
        limit = limits.get(
            field_name,
            40 if field_name == "email" else MAX_FORM_INPUT_LENGTH,
        )
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


# ---------------------------------------------------------------------------
# Detección de contenido malicioso en textos que terminan en un correo
# ---------------------------------------------------------------------------
# Un texto libre que se reenvía por correo puede usarse para: inyectar HTML/JS
# (XSS en el cliente de correo), inyectar cabeceras (Bcc:, Subject:...), colar
# enlaces de phishing, plantillas (SSTI / log4shell) o SQL/rutas. Se rechaza todo
# eso. El mensaje de error es genérico a propósito: no revela qué regla saltó.
_MALICIOUS_MESSAGE = (
    "El texto contiene contenido no permitido (código, etiquetas, enlaces o "
    "secuencias especiales). Describe la incidencia solo con texto simple."
)
_MALICIOUS_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in (
        r"[<>]",                                             # HTML / PHP / XML
        r"&#?[a-z0-9]{2,10};",                               # entidades: &lt; &#60; &#x3c;
        r"\\(?:x[0-9a-f]{2}|u[0-9a-f]{4}|[0-7]{3})",        # escapes \x3c \u003c \074
        r"\b(?:https?|ftp|file|ws|wss)\s*:\s*/",             # URLs con esquema
        r"\bwww\s*\.",                                       # URLs sin esquema
        r"\bdata\s*:\s*[a-z]+/",                             # data:text/html;...
        r"\bon[a-z]{3,20}\s*=",                              # onerror= onload= ...
        r"\{\{|\}\}|\{%|%\}|\$\{|\$\(|#\{",                # plantillas / sustitución de shell
        r"^\s*(?:bcc|cc|to|from|subject|reply-to|content-type|content-transfer-encoding|mime-version)\s*:",  # cabeceras
        r"\bunion\b.{0,40}\bselect\b",                      # SQL
        r"\b(?:drop|truncate|alter)\s+(?:table|database)\b",
        r"\bor\b\s+\d+\s*=\s*\d+",
        r"\.\./|\.\.\\|/etc/passwd|cmd\.exe|/bin/(?:ba)?sh\b",  # rutas / shell
        r"\b(?:eval|exec|system|popen|subprocess|__import__)\s*\(",  # ejecución de código
    )
)
_COMPACT_FORBIDDEN = ("javascript:", "vbscript:", "livescript:")


def _decoded_variants(value):
    """Texto original + normalizado (NFKC: ＜script＞ -> <script>) + decodificado (%3C -> <)."""
    normalized = unicodedata.normalize("NFKC", value)
    variants = [normalized]
    decoded = normalized
    for _ in range(2):  # doble codificación: %253C
        decoded = urllib.parse.unquote(decoded)
        variants.append(decoded)
    return variants


def validate_no_malicious_content(value):
    """Rechaza HTML/JS, URLs, inyección de cabeceras, plantillas, SQL y rutas sospechosas."""
    if value is None:
        return value
    for text in _decoded_variants(value):
        # Se quitan espacios y controles para detectar "java\nscript:".
        compact = re.sub(r"[\s\x00-\x1f\u200b-\u200f\u2060\ufeff]+", "", text.lower())
        if any(token in compact for token in _COMPACT_FORBIDDEN):
            raise ValidationError(_MALICIOUS_MESSAGE)
        if any(pattern.search(text) for pattern in _MALICIOUS_PATTERNS):
            raise ValidationError(_MALICIOUS_MESSAGE)
    return value

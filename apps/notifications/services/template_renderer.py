"""
Safe Notification Template Renderer and HTML Sanitizer.
Ensures strict placeholder validation, safe dynamic value escaping,
email subject header injection prevention, and HTML sanitization.
"""

from html import escape as escape_attribute
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.utils.html import escape

from .constants import SUPPORTED_PLACEHOLDERS, get_sample_context

PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")

ALLOWED_TAGS = {
    "p", "br", "hr", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span", "a", "blockquote", "code", "pre", "small",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target", "rel"},
    "th": {"align", "valign", "colspan", "rowspan", "style"},
    "td": {"align", "valign", "colspan", "rowspan", "style"},
    "table": {"border", "cellpadding", "cellspacing", "width", "style", "align"},
    "div": {"style", "class", "align"},
    "span": {"style", "class"},
    "p": {"style", "align"},
}

DISALLOWED_SCHEMES = ("javascript:", "vbscript:", "data:", "file:")


class HTMLSanitizer(HTMLParser):
    """
    Allowlist-based HTML sanitizer that strips dangerous tags (script, iframe, etc.),
    removes JavaScript pseudo-protocols from attributes, and drops unknown tags/attributes.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.suppress_content_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()

        # Completely strip content of dangerous container tags
        if tag_lower in {"script", "style", "iframe", "object", "embed", "applet"}:
            self.suppress_content_depth += 1
            return

        if self.suppress_content_depth > 0:
            return

        if tag_lower not in ALLOWED_TAGS:
            return  # skip disallowed tag

        allowed_attr_names = ALLOWED_ATTRIBUTES.get(tag_lower, set())
        clean_attrs: list[str] = []

        for name, value in attrs:
            name_lower = name.lower()
            if name_lower.startswith("on"):
                continue  # strip any event handlers (onclick, onload, etc.)

            if name_lower in allowed_attr_names and value is not None:
                val_stripped = value.strip().lower()
                # Only allow links with safe schemes. Placeholders are rendered
                # before sanitization so a token cannot bypass this check.
                if name_lower == "href":
                    if any(scheme in val_stripped for scheme in DISALLOWED_SCHEMES):
                        continue
                    scheme = urlsplit(val_stripped).scheme
                    if scheme and scheme not in {"http", "https", "mailto"}:
                        continue
                    # Force safe rel for links with target
                    if not any(a[0].lower() == "rel" for a in attrs):
                        clean_attrs.append('rel="noopener noreferrer"')

                # Basic inline style sanitization: prevent expression(), behavior, etc.
                if name_lower == "style":
                    if "expression" in val_stripped or "javascript:" in val_stripped or "url(" in val_stripped:
                        continue

                clean_attrs.append(
                    f'{name_lower}="{escape_attribute(value, quote=True)}"'
                )

        attr_str = f" {' '.join(clean_attrs)}" if clean_attrs else ""
        if tag_lower in {"br", "hr"}:
            self.output.append(f"<{tag_lower}{attr_str} />")
        else:
            self.output.append(f"<{tag_lower}{attr_str}>")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in {"script", "style", "iframe", "object", "embed", "applet"}:
            if self.suppress_content_depth > 0:
                self.suppress_content_depth -= 1
            return

        if self.suppress_content_depth > 0:
            return

        if tag_lower in ALLOWED_TAGS and tag_lower not in {"br", "hr"}:
            self.output.append(f"</{tag_lower}>")

    def handle_data(self, data: str):
        if self.suppress_content_depth == 0:
            self.output.append(escape(data))

    def handle_entityref(self, name: str):
        if self.suppress_content_depth == 0:
            self.output.append(f"&{name};")

    def handle_charref(self, name: str):
        if self.suppress_content_depth == 0:
            self.output.append(f"&#{name};")

    def get_clean_html(self) -> str:
        return "".join(self.output)


def sanitize_html(raw_html: str) -> str:
    """Sanitize arbitrary admin-authored HTML against allowlist."""
    if not raw_html:
        return ""
    sanitizer = HTMLSanitizer()
    sanitizer.feed(raw_html)
    sanitizer.close()
    return sanitizer.get_clean_html()


def html_to_plain_text(html_text: str) -> str:
    """Convert HTML content into clean, readable plain text."""
    if not html_text:
        return ""
    # Normalize line breaks and block endings
    text = re.sub(r"<(?:br|hr|\/p|\/tr|\/h[1-6]|\/li)[^>]*>", "\n", html_text, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities (&nbsp;, &amp;, etc.)
    text = unescape(text)
    # Collapse excess empty lines
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_placeholders(text: str) -> set[str]:
    """Find all placeholder keys `{key}` in the provided text."""
    if not text:
        return set()
    return set(PLACEHOLDER_PATTERN.findall(text))


def validate_placeholders(text: str, field_name: str = "template") -> None:
    """
    Ensure all placeholder tokens in `text` belong to SUPPORTED_PLACEHOLDERS.
    Raises ValidationError with a descriptive message if invalid tokens are found.
    """
    placeholders = extract_placeholders(text)
    allowed = set(SUPPORTED_PLACEHOLDERS.keys())
    unknown = placeholders - allowed
    if unknown:
        unknown_list = ", ".join(f"{{{k}}}" for k in sorted(unknown))
        allowed_list = ", ".join(f"{{{k}}}" for k in sorted(allowed))
        raise ValidationError(
            f"Invalid placeholders found in {field_name}: {unknown_list}. "
            f"Allowed placeholders are: {allowed_list}"
        )


def validate_subject(subject: str) -> None:
    """Validate email subject to prevent header injection attacks and empty subjects."""
    if not subject or not subject.strip():
        raise ValidationError("Subject cannot be empty.")
    if "\r" in subject or "\n" in subject:
        raise ValidationError("Subject cannot contain newline characters (CRLF injection prevention).")
    validate_placeholders(subject, field_name="subject")


def validate_template_content(subject: str, template_body: str) -> None:
    """Comprehensive validation of template subject and body."""
    validate_subject(subject)
    if not template_body or not template_body.strip():
        raise ValidationError("Template body cannot be empty.")
    validate_placeholders(template_body, field_name="template_body")


def render_template(
    subject_template: str,
    body_template: str,
    context: dict[str, Any] | None = None,
    sanitize: bool = True,
) -> tuple[str, str, str]:
    """
    Renders subject, HTML body, and plain text.
    - Validates placeholders.
    - Context dynamic values are HTML-escaped for HTML body.
    - Context dynamic values are raw for subject and text.
    - Admin-authored HTML in body_template is sanitized.
    Returns: (rendered_subject, rendered_html, rendered_text)
    """
    validate_template_content(subject_template, body_template)

    ctx = context or {}
    # Build safe plain context and safe HTML context
    plain_ctx: dict[str, str] = {}
    html_ctx: dict[str, str] = {}

    for key in SUPPORTED_PLACEHOLDERS:
        val = ctx.get(key)
        if val is None:
            val = ""
        val_str = str(val)
        plain_ctx[key] = val_str
        html_ctx[key] = escape(val_str)

    # 1. Render subject
    def replace_plain(match: re.Match) -> str:
        k = match.group(1)
        return plain_ctx.get(k, "")

    rendered_subject = PLACEHOLDER_PATTERN.sub(replace_plain, subject_template).strip()
    # Strip any stray newlines from dynamic values in subject as defensive measure
    rendered_subject = re.sub(r"[\r\n]+", " ", rendered_subject).strip()

    # Render before sanitizing so substituted attribute values are checked too.
    def replace_html(match: re.Match) -> str:
        k = match.group(1)
        return html_ctx.get(k, "")

    rendered_html = PLACEHOLDER_PATTERN.sub(replace_html, body_template)
    if sanitize:
        rendered_html = sanitize_html(rendered_html)

    rendered_text = html_to_plain_text(rendered_html)

    return rendered_subject, rendered_html, rendered_text


def preview_template(
    subject_template: str,
    body_template: str,
    custom_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Helper for previewing a template with sample context and optional overrides.
    """
    merged_ctx = get_sample_context()
    if custom_context:
        merged_ctx.update({k: str(v) for k, v in custom_context.items() if v is not None})

    subj, html_body, text_body = render_template(
        subject_template=subject_template,
        body_template=body_template,
        context=merged_ctx,
        sanitize=True,
    )
    return {
        "subject": subj,
        "html": html_body,
        "text": text_body,
    }

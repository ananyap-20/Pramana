"""Deliberately small declaration grammar, not a browser CSS implementation."""

import re

from app.repositories.visual_manifest import SELECTOR


PROPERTIES = {"color", "background-color", "font-size", "font-weight", "opacity",
              "background-image", "display", "visibility"}


def opaque_color(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    value = {"black": "#000000", "white": "#ffffff"}.get(value, value)
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return "#" + "".join(c * 2 for c in value[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    match = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value)
    if match and all(int(c) <= 255 for c in match.groups()):
        return "#" + "".join(f"{int(c):02x}" for c in match.groups())
    return None


def contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)


def declarations(text: str) -> tuple[dict[str, str], bool]:
    result = {}
    uncertain = False
    for declaration in text.split(";"):
        if not declaration.strip():
            continue
        key, separator, value = declaration.partition(":")
        key, value = key.strip().lower(), value.strip().lower()
        if not separator or key not in PROPERTIES or not value or any(c in value for c in "!{}\\/*\"'"):
            uncertain = True
        else:
            result[key] = value
    return result, uncertain


def stylesheet(text: str) -> tuple[list[tuple[str, dict[str, str]]], bool]:
    rules = []
    uncertain = False
    cursor = 0
    # No nested blocks, escapes, comments, at-rules, pseudo selectors or external imports.
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        if text[cursor:match.start()].strip():
            uncertain = True
        selector = match[1].strip()
        values, invalid = declarations(match[2])
        if not SELECTOR.fullmatch(selector):
            uncertain = True
        else:
            rules.append((selector, values))
        uncertain |= invalid
        cursor = match.end()
    return rules, uncertain or bool(text[cursor:].strip())


def matches(selector: str, tag: str, attrs: dict) -> bool:
    if selector.startswith("#"):
        return attrs.get("id") == selector[1:]
    if selector.startswith("."):
        return selector[1:] in (attrs.get("class") or "").split()
    return tag == selector


def resolve_style(tag: str, attrs: dict, rules: list) -> tuple[dict[str, str], bool]:
    matched = [(1 if s.startswith("#") else 0, 1 if s.startswith(".") else 0, i, values)
               for i, (s, values) in enumerate(rules) if matches(s, tag, attrs)]
    style = {}
    for _, _, _, values in sorted(matched):
        style.update(values)
    inline, invalid = declarations(attrs.get("style") or "")
    style.update(inline)
    return style, invalid


def font_metrics(style: dict) -> tuple[float | None, int | None]:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(px|pt)", style.get("font-size", ""))
    size = float(match[1]) * (4 / 3 if match[2] == "pt" else 1) if match else None
    weight = {"normal": "400", "bold": "700"}.get(style.get("font-weight"), style.get("font-weight", ""))
    return size if size and size <= 1000 else None, int(weight) if re.fullmatch(r"[1-9]00", weight) else None

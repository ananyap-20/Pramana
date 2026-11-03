"""Read-only operator-managed approved manifest; never populated by a draft upload."""

import re
from pathlib import Path

from app.visual_models import VisualManifest


SELECTOR = re.compile(r"(?:[a-z][a-z0-9]*|[.#][A-Za-z_][A-Za-z0-9_-]*)\Z")


def validate_manifest(manifest: VisualManifest) -> VisualManifest:
    from app.services.visual_css import opaque_color

    selectors = (*manifest.logo_selectors, *(x.selector for x in manifest.palette),
                 *(x.selector for x in manifest.text_exemptions))
    if any(not SELECTOR.fullmatch(s) for s in selectors):
        raise ValueError("Manifest selectors must be a tag, .class or #id.")
    if any(not re.fullmatch(r"[a-f0-9]{64}", s) for s in manifest.logo_sha256):
        raise ValueError("Manifest logo digests must be lowercase SHA-256.")
    if any(opaque_color(c) is None for p in manifest.palette for c in p.colors):
        raise ValueError("Manifest palette colors must be supported opaque sRGB colors.")
    if manifest.source_excerpt not in manifest.source_text:
        raise ValueError("Manifest excerpt must exist in its source version.")
    return manifest


class VisualManifestRepository:
    def __init__(self, path: str | None = None):
        self._manifest = None
        # Like the seeded text rules, this policy applies only to fictional LumaDesk.
        if path is None:
            path = str(Path(__file__).resolve().parents[1] / "data/lumadesk-visual-demo.json")
        if path:
            source = Path(path)
            with source.open("rb") as handle:
                content = handle.read(65537)
            if len(content) > 65536:
                raise ValueError("Visual manifest exceeds 64 KiB.")
            self._manifest = validate_manifest(VisualManifest.model_validate_json(content))

    def get(self, brand_id: str) -> VisualManifest | None:
        m = self._manifest
        return m if m and m.brand_id == brand_id and m.approved and m.active else None

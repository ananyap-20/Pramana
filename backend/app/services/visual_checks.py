"""Passive bounded HTML/declaration inspection; never renders or executes HTML."""

import base64
from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json

from PIL import Image, JpegImagePlugin, PngImagePlugin  # Register only the permitted formats.

from app.domain import EvidenceStatus as Status
from app.services.visual_css import (contrast_ratio, font_metrics, matches, opaque_color,
                                     resolve_style, stylesheet)
from app.visual_models import VisualFinding, VisualManifest, VisualRequest, VisualResponse


class VisualInputError(ValueError):
    pass


TAGS = {"html", "head", "body", "main", "section", "article", "header", "footer", "nav",
        "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i",
        "ul", "ol", "li", "a", "button", "label", "img", "br", "hr"}
VOID = {"img", "br", "hr"}
ATTRS = {"id", "class", "style", "alt", "src", "role", "aria-hidden", "aria-label", "hidden",
         "disabled", "title", "href", "lang", "dir"}


@dataclass
class Node:
    tag: str
    attrs: dict
    quote: str
    parent: int | None
    text: bool = False
    style: dict = field(default_factory=dict)


class PassiveHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes: list[Node] = []
        self.stack: list[int] = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS or len(attrs) > 32 or len(self.nodes) >= 1000 or len(self.stack) >= 32:
            raise VisualInputError("Unsupported HTML or DOM limit exceeded.")
        values = {}
        for key, value in attrs:
            if key not in ATTRS or key in values or (value is not None and len(value) > 2048):
                raise VisualInputError("Unsupported or duplicate HTML attribute.")
            values[key] = value or ""
        if "src" in values and (tag != "img" or not values["src"].startswith("asset:")):
            raise VisualInputError("Images must reference supplied asset IDs using asset:ID.")
        if "href" in values and not values["href"].startswith("#"):
            raise VisualInputError("Only inert fragment links are supported.")
        if values.get("id"):
            if values["id"] in self.ids:
                raise VisualInputError("Duplicate HTML IDs are unsupported.")
            self.ids.add(values["id"])
        self.nodes.append(Node(tag, values, self.get_starttag_text(), self.stack[-1] if self.stack else None))
        if tag not in VOID:
            self.stack.append(len(self.nodes) - 1)

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID:
            raise VisualInputError("Only void HTML elements may self-close.")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if not self.stack or self.nodes[self.stack[-1]].tag != tag:
            raise VisualInputError("Use explicitly balanced supported HTML.")
        self.stack.pop()

    def handle_data(self, data):
        if data.strip():
            if not self.stack:
                raise VisualInputError("Text must be inside an HTML element.")
            self.nodes[self.stack[-1]].text = True

    def handle_decl(self, decl):
        if decl.lower() != "doctype html":
            raise VisualInputError("Only the HTML doctype is supported.")

    def unknown_decl(self, data):
        raise VisualInputError("Unsupported HTML declaration.")

    def handle_pi(self, data):
        raise VisualInputError("Processing instructions are unsupported.")


def asset_digests(request: VisualRequest) -> dict[str, str]:
    digests = {}
    total = 0
    for asset in request.assets:
        try:
            content = base64.b64decode(asset.content_base64, validate=True)
            total += len(content)
            if total > 384 * 1024:
                raise VisualInputError("Combined assets exceed 384 KiB.")
            expected = "PNG" if asset.media_type == "image/png" else "JPEG"
            with Image.open(BytesIO(content), formats=["PNG", "JPEG"]) as image:
                if image.format != expected or image.width * image.height > 1_000_000 or getattr(image, "n_frames", 1) != 1:
                    raise ValueError()
                image.verify()
            with Image.open(BytesIO(content), formats=["PNG", "JPEG"]) as image:
                image.load()
        except VisualInputError:
            raise
        except Exception:
            raise VisualInputError("Invalid asset: only single-frame PNG/JPEG up to one million pixels is supported.") from None
        digests[asset.asset_id] = hashlib.sha256(content).hexdigest()
    return digests


def analyze_visual(request: VisualRequest, manifest: VisualManifest) -> VisualResponse:
    digests = asset_digests(request)
    parser = PassiveHTML()
    parser.feed(request.html)
    parser.close()
    if parser.stack or not parser.nodes:
        raise VisualInputError("Use explicitly balanced, nonempty supported HTML.")
    rules, css_uncertain = stylesheet(request.css)
    for node in parser.nodes:
        node.style, invalid = resolve_style(node.tag, node.attrs, rules)
        css_uncertain |= invalid
    findings = []

    def add(check, index, status, result, explanation, **evidence):
        if len(findings) >= 1000:
            raise VisualInputError("Visual findings exceed the 1000-result safety limit.")
        node = parser.nodes[index]
        findings.append(VisualFinding(
            check=check, rule_version="WCAG-2.2-1.4.3-static-v1" if check == "contrast" else f"pramana-{check}-static-v1",
            element=f"node:{index + 1}:{node.tag}", evidence_status=status, result=result,
            explanation=explanation, evidence={"html_start_tag": node.quote, **evidence}))

    for index, node in enumerate(parser.nodes):
        chain = [node]
        ancestor = node.parent
        while ancestor is not None:
            chain.append(parser.nodes[ancestor])
            ancestor = parser.nodes[ancestor].parent
        if node.tag == "img":
            asset_id = node.attrs.get("src", "").removeprefix("asset:")
            if asset_id not in digests:
                raise VisualInputError("Every image must reference a supplied valid asset.")
            logo = any(matches(s, node.tag, node.attrs) for s in manifest.logo_selectors)
            if logo:
                exact = digests[asset_id] in manifest.logo_sha256
                add("logo", index, Status.SUPPORTED if exact else Status.UNSUPPORTED,
                    "exact_digest_match" if exact else "digest_not_listed",
                    "Exact bytes only; altered or flattened logo recognition is not performed.",
                    asset_id=asset_id, sha256=digests[asset_id])
            alt = node.attrs.get("alt")
            interactive = any(n.tag in {"a", "button"} or n.attrs.get("role", "") not in {"", "none", "presentation"}
                              for n in chain[1:])
            role = node.attrs.get("role", "").lower()
            if alt == "" and not interactive and role in {"", "presentation", "none"} and not node.attrs.get("aria-label"):
                status, result = Status.SUPPORTED, "declared_decorative"
            elif alt and alt.strip() and role not in {"presentation", "none"} and node.attrs.get("aria-hidden") != "true":
                status, result = Status.SUPPORTED, "description_present_quality_unverified"
            elif role in {"presentation", "none"} or node.attrs.get("aria-label") or node.attrs.get("aria-hidden") == "true":
                status, result = Status.INDETERMINATE, "semantics_need_review"
            else:
                status, result = Status.UNSUPPORTED, "missing_description"
            add("alt_text", index, status, result,
                "Checks declared description/decorative intent only; meaning and description quality require human review.",
                asset_id=asset_id, alt=alt, interactive=interactive)

        for target in manifest.palette:
            if matches(target.selector, node.tag, node.attrs):
                color = opaque_color(node.style.get(target.property))
                allowed = [opaque_color(c) for c in target.colors]
                uncertain = css_uncertain or color is None
                add("palette", index, Status.INDETERMINATE if uncertain else Status.SUPPORTED if color in allowed else Status.CONTRADICTED,
                    "unresolved_declaration" if uncertain else "approved_color" if color in allowed else "unapproved_color",
                    "Configured declaration only; photograph pixels and rendered appearance are not measured.",
                    selector=target.selector, property=target.property, declared=node.style.get(target.property),
                    normalized=color, allowed_colors=",".join(allowed))

        if not node.text:
            continue
        style = node.style
        foreground, background = opaque_color(style.get("color")), opaque_color(style.get("background-color"))
        size, weight = font_metrics(style)
        exempt = None
        if not css_uncertain and any("hidden" in n.attrs and n.attrs["hidden"] in {"", "hidden"}
                                     and n.style.get("display", "none") == "none" for n in chain):
            exempt = "hidden_attribute"
        elif any(n.tag == "button" and "disabled" in n.attrs for n in chain):
            exempt = "inactive_control"
        else:
            for exemption in manifest.text_exemptions:
                if any(matches(exemption.selector, n.tag, n.attrs) for n in chain):
                    exempt = exemption.reason
        # Require explicit declarations on the text-bearing node. Inheritance, UA styles,
        # layout, overlays and pseudo states are outside this static measurement contract.
        uncertain = css_uncertain or not all((foreground, background, size, weight))
        uncertain |= any(n.style.get("opacity", "1") != "1" or
                         n.style.get("background-image", "none") != "none" or
                         n.style.get("visibility", "visible") != "visible" or
                         n.style.get("display", "block") not in {"block", "inline", "inline-block", "none"}
                         for n in chain)
        threshold = 3.0 if size and weight and (size >= 24 or (size >= 14 * (4 / 3) and weight >= 700)) else 4.5
        ratio = None
        if exempt:
            status, result = Status.SUPPORTED, "exempt"
        elif uncertain or any(n.style.get("display") == "none" for n in chain):
            status, result = Status.INDETERMINATE, "unresolved_compositing_or_style"
        else:
            ratio = contrast_ratio(foreground, background)
            status = Status.SUPPORTED if ratio >= threshold else Status.CONTRADICTED
            result = "declared_pair_meets_threshold" if ratio >= threshold else "declared_pair_below_threshold"
        add("contrast", index, status, result,
            "WCAG 2.2 AA declared color-pair calculation only; rendered appearance and full compliance are unverified.",
            foreground=foreground or style.get("color"), background=background or style.get("background-color"),
            font_size_px=size, font_weight=weight, ratio=ratio, threshold=threshold, exemption=exempt)

    # Missing configured elements must not silently look like a successful brand check.
    for check, selector in [("logo", s) for s in manifest.logo_selectors] + [("palette", p.selector) for p in manifest.palette]:
        if not any(matches(selector, n.tag, n.attrs) and (check != "logo" or n.tag == "img") for n in parser.nodes):
            findings.append(VisualFinding(check=check,
                rule_version="pramana-target-static-v1", element=selector, evidence_status=Status.INDETERMINATE,
                result="configured_target_absent", explanation="No matching element was supplied.", evidence={"selector": selector}))
    if len(findings) > 1000:
        raise VisualInputError("Visual findings exceed the 1000-result safety limit.")
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    manifest_canonical = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return VisualResponse(brand_id=request.brand_id, draft_id=request.draft_id, draft_version=request.draft_version,
        input_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(), manifest_version=manifest.version,
        manifest_sha256=hashlib.sha256(manifest_canonical.encode("utf-8")).hexdigest(),
        source_id=manifest.source_id, source_version=manifest.source_version, source_excerpt=manifest.source_excerpt,
        assets_sha256=digests, findings=tuple(findings), limitations=(
            "Static declarations only; no renderer, scripts, network, layout, pseudo states or full WCAG evaluation.",
            "Contrast requires explicit opaque foreground/background and px/pt size plus weight on the text-bearing element.",
            "Exact asset bytes only; no altered/flattened logo recognition or photograph palette analysis.",
            "Alt presence and declared decorative intent do not establish description quality or actual intent.",
            "Ephemeral analysis; caller must retain the exact request/version for replay. Human approval remains required.",
        ))

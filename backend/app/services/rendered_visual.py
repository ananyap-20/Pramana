"""Computed visual measurements in a disposable, offline Chromium context."""

import html
import re

from app.domain import EvidenceStatus as S
from app.services.visual_checks import PassiveHTML, VisualInputError, analyze_visual
from app.services.visual_css import matches
from app.visual_models import VisualFinding


class RenderHTML(PassiveHTML):
    def __init__(self, assets):
        super().__init__()
        self.output = []
        self.assets = assets

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        node = self.nodes[-1]
        values = dict(node.attrs)
        if tag == "img":
            asset = self.assets[values["src"].removeprefix("asset:")]
            values["src"] = f"data:{asset.media_type};base64,{asset.content_base64}"
        values["data-pramana-node"] = str(len(self.nodes) - 1)
        self.output.append("<" + tag + " " + " ".join(
            f'{key}="{html.escape(value, quote=True)}"' for key, value in values.items()) + ">")

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        super().handle_data(data)
        self.output.append(html.escape(data))


def rgba(value):
    match = re.fullmatch(r"rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)", value)
    if not match:
        return None
    return (*map(int, match.groups()[:3]), float(match[4] or 1))


def composite(top, bottom):
    return tuple(top[i] * top[3] + bottom[i] * (1 - top[3]) for i in range(3))


def hex_color(value):
    return "#" + "".join(f"{round(c):02x}" for c in value[:3])


def ratio_of(foreground, background):
    # Retain unrounded compositing values at the threshold boundary.
    def luminance(color):
        def channel(c):
            c /= 255
            return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
        return sum(channel(c) * weight for c, weight in zip(color, (.2126, .7152, .0722)))
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + .05) / (low + .05)


MEASURE = """() => {
  const elements = [...document.querySelectorAll('[data-pramana-node]')];
  const rect = e => { const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  return elements.map(e => {
    const style=getComputedStyle(e), chain=[];
    for(let n=e;n;n=n.parentElement) chain.unshift(n);
    let r=e.getBoundingClientRect();
    if(!r.width || !r.height){const range=document.createRange();range.selectNodeContents(e);r=range.getBoundingClientRect();}
    const overlaps=elements.some(other => {
      if(other===e || e.contains(other) || other.contains(e)) return false;
      const s=getComputedStyle(other), b=other.getBoundingClientRect();
      return s.display!=='none' && s.visibility==='visible' && Number(s.opacity)>0 &&
        (['absolute','fixed','sticky'].includes(s.position) || s.zIndex!=='auto') &&
        b.width>0 && b.height>0 && r.left<b.right && r.right>b.left && r.top<b.bottom && r.bottom>b.top;
    });
    const effects=chain.some(n => {
      const s=getComputedStyle(n);
      return s.opacity!=='1' || s.backgroundImage!=='none' || s.filter!=='none' ||
        s.backdropFilter!=='none' || s.mixBlendMode!=='normal' || s.transform!=='none' ||
        s.textShadow!=='none' || s.backgroundClip==='text' || s.animationName!=='none' ||
        s.transitionDuration.split(',').some(value=>parseFloat(value)!==0) ||
        s.webkitTextFillColor!==s.color || parseFloat(s.webkitTextStrokeWidth)>0 ||
        s.maskImage!=='none' || s.clipPath!=='none' || s.contentVisibility!=='visible' ||
        ['::before','::after'].some(p => !['none','normal','""'].includes(getComputedStyle(n,p).content));
    });
    return {index:Number(e.dataset.pramanaNode), color:style.color, background:style.backgroundColor,
      backgrounds:chain.map(n=>getComputedStyle(n).backgroundColor),
      size:parseFloat(style.fontSize), weight:Number(style.fontWeight), bounds:rect(e),
      visible:r.width>0 && r.height>0 && chain.every(n=>{
        const s=getComputedStyle(n);return s.display!=='none' && s.visibility==='visible';}),
      disabled:chain.some(n=>n.tagName==='BUTTON' && n.disabled), uncertain:effects||overlaps};
  });
}"""


def analyze_rendered(request, manifest):
    from playwright.sync_api import sync_playwright
    base = analyze_visual(request, manifest)  # Passive HTML/assets validation and exact evidence.
    if "data-pramana-node" in request.css or "\\" in request.css or "<" in request.css or re.search(r"@(?:import|font-face|namespace)|url\s*\(", request.css, re.I):
        raise VisualInputError("Rendered CSS cannot fetch URLs, load fonts or contain escaped rules.")
    parser = RenderHTML({asset.asset_id: asset for asset in request.assets})
    parser.feed(request.html)
    parser.close()
    # Inline declarations cannot bypass the stylesheet URL restrictions.
    if any(re.search(r"url\s*\(|@import|\\", node.attrs.get("style", ""), re.I) for node in parser.nodes):
        raise VisualInputError("Inline CSS cannot fetch URLs or contain escaped rules.")
    document = "<!doctype html><style>html{background:white}</style><style>" + request.css + "</style>" + "".join(parser.output)
    blocked = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, chromium_sandbox=True,
            args=["--disable-background-networking", "--disable-component-update", "--no-first-run"])
        try:
            context = browser.new_context(java_script_enabled=False, service_workers="block", accept_downloads=False,
                viewport={"width": request.viewport_width, "height": request.viewport_height},
                reduced_motion="reduce", locale="en-US", device_scale_factor=1)
            def route_request(route):
                if route.request.url == "https://pramana.invalid/render" and route.request.is_navigation_request():
                    route.fulfill(body=document, content_type="text/html", headers={"Content-Security-Policy":
                        "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"})
                else:
                    blocked.append(True)
                    route.abort()
            context.route("**/*", route_request)
            page = context.new_page()
            page.goto("https://pramana.invalid/render", wait_until="load", timeout=8000)
            # Only this application-owned measurement program executes through DevTools.
            measurements = page.evaluate(MEASURE)
            browser_version = browser.version
        finally:
            browser.close()
    by_index = {item["index"]: item for item in measurements}
    findings = [f for f in base.findings if f.check in {"logo", "alt_text"} or f.result == "configured_target_absent"]
    def add(check, index, status, result, **evidence):
        findings.append(VisualFinding(check=check, rule_version="WCAG-2.2-1.4.3-rendered-v1" if check=="contrast" else "pramana-palette-rendered-v1",
            element=f"node:{index+1}:{parser.nodes[index].tag}", evidence_status=status, result=result,
            explanation="Computed browser measurement for this exact supplied input and viewport; human review remains required.",
            evidence={"html_start_tag": parser.nodes[index].quote, **evidence}))
    for index, node in enumerate(parser.nodes):
        item = by_index.get(index)
        if item is None:
            if node.text:
                add("contrast", index, S.INDETERMINATE, "browser_structure_changed")
            continue
        for target in manifest.palette:
            if matches(target.selector, node.tag, node.attrs):
                from app.services.visual_css import opaque_color
                actual = rgba(item["color"] if target.property=="color" else item["background"])
                allowed = [opaque_color(color) for color in target.colors]
                uncertain = actual is None or actual[3]!=1 or item["uncertain"] or not item["visible"]
                normalized = hex_color(actual) if actual else None
                add("palette", index, S.INDETERMINATE if uncertain else S.SUPPORTED if normalized in allowed else S.CONTRADICTED,
                    "unresolved_compositing" if uncertain else "approved_color" if normalized in allowed else "unapproved_color",
                    selector=target.selector, property=target.property, computed=normalized, allowed_colors=",".join(allowed))
        if not node.text:
            continue
        foreground=rgba(item["color"])
        backgrounds=[rgba(value) for value in item["backgrounds"]]
        ratio=None
        threshold=3.0 if item["size"]>=24 or item["size"]>=14*4/3 and item["weight"]>=700 else 4.5
        exempt="not_visible" if not item["visible"] else "inactive_control" if item["disabled"] else None
        ancestor=index
        while exempt is None and ancestor is not None:
            n=parser.nodes[ancestor]
            exempt=next((e.reason for e in manifest.text_exemptions if matches(e.selector,n.tag,n.attrs)),None)
            ancestor=n.parent
        uncertain=item["uncertain"] or foreground is None or any(value is None for value in backgrounds)
        if exempt:
            status,result=S.SUPPORTED,"exempt"
        elif uncertain:
            status,result=S.INDETERMINATE,"unresolved_compositing_or_effect"
        else:
            background=(255,255,255)
            for value in backgrounds:
                background=composite(value,background)
            foreground=composite(foreground,background)
            ratio=ratio_of(foreground,background)
            status=S.SUPPORTED if ratio>=threshold else S.CONTRADICTED
            result="computed_pair_meets_threshold" if ratio>=threshold else "computed_pair_below_threshold"
        add("contrast",index,status,result,foreground=item["color"],backgrounds=" | ".join(item["backgrounds"]),
            font_size_px=item["size"],font_weight=item["weight"],ratio=ratio,threshold=threshold,exemption=exempt,
            **{f"bounds_{key}":value for key,value in item["bounds"].items()})
    if len(findings)>1000:
        raise VisualInputError("Visual findings exceed the 1000-result safety limit.")
    return base.model_copy(update={"mode":"rendered","findings":tuple(findings),
        "rendering":{"engine":"Chromium","browser_version":browser_version,"viewport_width":request.viewport_width,
            "viewport_height":request.viewport_height,"scripts_enabled":False,"outbound_requests_blocked":True,
            "blocked_request_count":len(blocked)},
        "limitations":("Computed styles at the recorded viewport; no full WCAG certification or subjective layout judgment.",
            "Gradients, image backgrounds, opacity, overlays, transforms, filters and generated content remain indeterminate.",
            "Exact logo bytes only; altered/flattened recognition and alt-description quality need human review.",
            "Supplied scripts and external requests are disabled. Native browser/process isolation is not proof against all browser vulnerabilities.")})

"""UI/UX design generator — produces a ready-to-run HTML page with CSS animations.

Given a short description (and optional style preset) JARVIS writes a complete,
self-contained HTML file (inline CSS + tiny JS, zero external dependencies) that
implements a modern UI design with animated elements. The user can open the file
in any browser to preview, use, or extend the design.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from ultron.tools.base import Tool

OUTPUT_DIR = Path.home() / ".ultron" / "generated_ui"

PRESETS = {
    "jarvis": "jarvis",
    "neon": "neon",
    "glass": "glass",
    "minimal": "minimal",
}

# Shared keyframes included in every generated page.
_KEYFRAMES = """
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes glow{0%,100%{opacity:.55;transform:scale(1)}50%{opacity:1;transform:scale(1.06)}}
@keyframes gradShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes ping{0%,100%{transform:scale(1);opacity:.7}50%{transform:scale(1.6);opacity:0}}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes pulseBar{0%{width:4%}50%{width:78%}100%{width:12%}}
@keyframes ripple{to{transform:scale(4);opacity:0}}
@keyframes blink{50%{opacity:0}}
"""

# Theme palettes: each defines the design tokens injected into the page.
_THEMES = {
    "jarvis": {
        "bg": "#04070a",
        "panel": "rgba(10,18,20,0.55)",
        "accent": "#3dffb0",
        "accent2": "#4de0ff",
        "text": "#dff2ec",
        "muted": "#5f7d78",
        "font": "'Segoe UI', system-ui, sans-serif",
        "radius": "16px",
    },
    "neon": {
        "bg": "#08010f",
        "panel": "rgba(24,6,40,0.55)",
        "accent": "#ff4dd8",
        "accent2": "#ffca3d",
        "text": "#ffeafe",
        "muted": "#9a7fb8",
        "font": "'Segoe UI', system-ui, sans-serif",
        "radius": "18px",
    },
    "glass": {
        "bg": "#0c1220",
        "panel": "rgba(255,255,255,0.08)",
        "accent": "#8ab4ff",
        "accent2": "#7ee8fa",
        "text": "#eef3ff",
        "muted": "#93a5c8",
        "font": "'Segoe UI', system-ui, sans-serif",
        "radius": "20px",
    },
    "minimal": {
        "bg": "#f4f6f8",
        "panel": "rgba(255,255,255,0.85)",
        "accent": "#111827",
        "accent2": "#3b82f6",
        "text": "#111827",
        "muted": "#6b7280",
        "font": "'Segoe UI', system-ui, sans-serif",
        "radius": "12px",
    },
}

def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "ui-design"


class GenerateUI(Tool):
    """Generate a complete UI/UX design with animations as a runnable HTML file."""

    name = "generate_ui"
    description = (
        "Generate a complete, ready-to-run HTML/CSS UI design with animations for coding work. "
        "Provide a description of the page/component you want (e.g. 'landing page for my AI startup', "
        "'dashboard with live stats', 'login card with a glowing button') and an optional style preset "
        "('jarvis', 'neon', 'glass', 'minimal'). JARVIS writes a self-contained HTML file to your "
        "generated_ui folder that you can open directly in a browser."
    )
    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "What to design: page type, sections, and vibe.",
            },
            "preset": {
                "type": "string",
                "description": "Visual style preset.",
                "enum": ["jarvis", "neon", "glass", "minimal"],
                "default": "jarvis",
            },
            "output_file": {
                "type": "string",
                "description": "Optional custom output path (otherwise a file is auto-created under generated_ui/).",
            },
        },
        "required": ["description"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "output_file": {"type": "string"},
            "title": {"type": "string"},
            "preset": {"type": "string"},
            "snippet": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        description: str,
        preset: str = "jarvis",
        output_file: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        description = (description or "").strip()
        if not description:
            return {"success": False, "error": "Missing 'description' parameter."}

        preset = (preset or "jarvis").lower()
        if preset not in PRESETS:
            return {"success": False, "error": f"Unknown preset '{preset}'. Choose from: jarvis, neon, glass, minimal."}

        theme = _THEMES[preset]
        doc = self._build_page(description, preset, theme)

        try:
            out = Path(output_file).expanduser() if output_file else OUTPUT_DIR / f"{_slug(description)}.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(doc, encoding="utf-8")
        except OSError as exc:
            return {"success": False, "error": f"Could not write output file: {exc}"}

        snippet = "```html\n" + "\n".join(doc.splitlines()[30:55]) + "\n```"

        title = self._title_of(description)
        return {
            "success": True,
            "output_file": str(out),
            "title": title,
            "preset": preset,
            "snippet": snippet,
        }

    @staticmethod
    def _title_of(description: str) -> str:
        words = [w for w in description.split() if w[0].isalnum()][:5]
        return " ".join(words).title() if words else "UI Design"

    def _build_page(self, description: str, preset: str, theme: Dict[str, str]) -> str:
        t = theme
        title = self._title_of(description)
        is_dark = preset in {"jarvis", "neon", "glass"}
        body_text = t["text"]
        shadow_text = t["muted"]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Generated UI</title>
<style>
:root{{
  --bg:{t['bg']};
  --panel:{t['panel']};
  --accent:{t['accent']};
  --accent2:{t['accent2']};
  --text:{t['text']};
  --muted:{t['muted']};
  --radius:{t['radius']};
  --shadow-pop:0 18px 50px rgba(0,0,0,.35);
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  min-height:100vh;
  background:var(--bg);
  color:var(--text);
  font-family:{t['font']};
  overflow-x:hidden;
  background-image:
    radial-gradient(60rem 40rem at 15% -10%, color-mix(in srgb, var(--accent) 14%, transparent), transparent),
    radial-gradient(50rem 36rem at 110% 20%, color-mix(in srgb, var(--accent2) 12%, transparent), transparent);
}}
/* animated headline gradient */
.grad-text{{
  background:linear-gradient(90deg, var(--accent), var(--accent2), var(--accent));
  background-size:250% 100%;
  -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; color:transparent;
  animation:gradShift 6s ease infinite;
}}
/* floating ambient orbs */
.orb{{
  position:fixed; border-radius:50%; filter:blur(70px); z-index:-1; animation:floaty 9s ease-in-out infinite;
  background:color-mix(in srgb, var(--accent) 18%, transparent);
}}
.orb.a{{width:34vw;height:34vw;top:-12vw;left:-8vw}}
.orb.b{{width:28vw;height:28vw;bottom:-10vw;right:-6vw;background:color-mix(in srgb, var(--accent2) 16%, transparent);animation-delay:-4s}}
.wrap{{max-width:1080px;margin:0 auto;padding:clamp(24px,6vw,72px) 22px}}
.hero{{text-align:center;animation:fadeUp .8s cubic-bezier(.22,.8,.36,1) both}}
.tag{{
  display:inline-flex;align-items:center;gap:8px;
  font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent);
  border:1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  background:color-mix(in srgb, var(--accent) 9%, transparent);
  padding:7px 15px;border-radius:999px;margin-bottom:22px;position:relative;
}}
.tag .dot{{width:7px;height:7px;border-radius:50%;background:var(--accent);animation:blink 1.6s infinite}}
h1{{font-size:clamp(2rem,5.4vw,4rem);line-height:1.08;font-weight:800;letter-spacing:-.02em;margin-bottom:18px}}
.sub{{font-size:clamp(.95rem,2vw,1.2rem);color:var(--muted);max-width:620px;margin:0 auto 34px;line-height:1.6}}
.btn{{display:inline-block;cursor:pointer;position:relative;overflow:hidden;
  padding:14px 30px;border:0;border-radius:999px;font-weight:700;letter-spacing:.04em;
  font-size:.95rem;background:linear-gradient(120deg,var(--accent),var(--accent2));
  color:{'#04120c' if is_dark else '#fff'};transition:transform .18s ease, box-shadow .18s ease;
  box-shadow:0 10px 30px color-mix(in srgb, var(--accent) 34%, transparent);}}
.btn:hover{{transform:translateY(-2px);box-shadow:0 16px 40px color-mix(in srgb, var(--accent) 46%, transparent)}}
.btn.ghost{{background:transparent;border:1px solid color-mix(in srgb, var(--accent) 50%, transparent);
  color:var(--accent);box-shadow:none}}
.btn .ripple{{position:absolute;border-radius:50%;transform:scale(0);background:rgba(255,255,255,.55);animation:ripple .7s linear;width:20px;height:20px;pointer-events:none}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:16px;margin-top:64px}}
.card{{
  background:var(--panel);
  border:1px solid color-mix(in srgb, var(--accent) 18%, transparent);
  border-radius:var(--radius);
  padding:26px;backdrop-filter:blur(14px);
  animation:fadeUp .7s cubic-bezier(.22,.8,.36,1) both;opacity:0;
  transition:transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}}
.card:hover{{transform:translateY(-6px);border-color:color-mix(in srgb, var(--accent) 55%, transparent);box-shadow:var(--shadow-pop)}}
.card:nth-child(1){{animation-delay:.15s}}.card:nth-child(2){{animation-delay:.3s}}
.card:nth-child(3){{animation-delay:.45s}}.card:nth-child(4){{animation-delay:.6s}}
.card .ic{{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;
  background:color-mix(in srgb, var(--accent) 14%, transparent);color:var(--accent);margin-bottom:16px}}
.card h3{{font-size:1.05rem;margin-bottom:8px}}
.card p{{font-size:.9rem;color:var(--muted);line-height:1.55}}
.progress{{margin-top:52px;animation:fadeUp .8s .7s both;opacity:0}}
.progress .row{{display:flex;justify-content:space-between;font-size:12px;letter-spacing:.12em;margin-bottom:8px;color:var(--muted)}}
.track{{height:10px;border-radius:999px;background:color-mix(in srgb, var(--accent) 12%, transparent);overflow:hidden}}
.bar{{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent2));animation:pulseBar 3.4s ease-in-out infinite}}
.loader{{width:46px;height:46px;margin:64px auto 0;border:4px solid color-mix(in srgb, var(--accent) 22%, transparent);
  border-top-color:var(--accent);border-radius:50%;animation:spin 1s linear infinite;position:relative}}
.loader::after{{content:'';position:absolute;inset:-14px;border:1px solid color-mix(in srgb, var(--accent2) 24%, transparent);border-radius:50%;animation:ping 2s ease-out infinite}}
.stats{{display:flex;justify-content:center;gap:clamp(18px,4vw,48px);margin-top:58px;flex-wrap:wrap}}
.stat{{text-align:center;animation:fadeUp .8s .9s both;opacity:0}}
.stat .n{{font-size:clamp(1.6rem,3vw,2.4rem);font-weight:800;color:var(--accent)}}
.stat .l{{font-size:11px;letter-spacing:.14em;color:var(--muted);text-transform:uppercase}}
.empty{{margin-top:64px;text-align:center;color:var(--muted);font-size:14px}}
{_KEYFRAMES}
</style>
</head>
<body>
<div class="orb a"></div><div class="orb b"></div>
<main class="wrap">
<header class="hero">
  <span class="tag"><span class="dot"></span>{escape_xml(description[:60])}</span>
  <h1 class="grad-text">{title}</h1>
  <p class="sub">A self-contained UI/UX concept generated by JARVIS. Open this file in your browser to preview — it is fully editable and dependency-free.</p>
  <div>
    <button class="btn" id="btn-main">Get started <span class="ripple"></span></button>
    <button class="btn ghost">Learn more</button>
  </div>
</header>

<section class="grid">
  <div class="card"><div class="ic">⚡</div><h3>Fast</h3><p>Lightweight, dependency-free markup and CSS that loads instantly on any device.</p></div>
  <div class="card"><div class="ic">🎬</div><h3>Animated</h3><p>Keyframe-driven motion: glow, fade-up stagger, pulsing bars and ambient orbs.</p></div>
  <div class="card"><div class="ic">🖌️</div><h3>Customizable</h3><p>Design tokens via CSS variables — change one color and the whole theme follows.</p></div>
  <div class="card"><div class="ic">📐</div><h3>Responsive</h3><p>Fluid grids and clamp() typography adapt from phone to widescreen.</p></div>
</section>

<div class="progress">
  <div class="row"><span>SYSTEM LOAD</span><span>CPU 42% · MEM 68%</span></div>
  <div class="track"><div class="bar"></div></div>
</div>
<div class="loader"></div>

<section class="stats">
  <div class="stat"><div class="n">3.2x</div><div class="l">Faster workflow</div></div>
  <div class="stat"><div class="n">100%</div><div class="l">Self-contained</div></div>
  <div class="stat"><div class="n">24/7</div><div class="l">Always on</div></div>
</section>
</main>

<script>
document.querySelectorAll('.btn').forEach(btn=>{{
  btn.addEventListener('click',e=>{{
    const r=document.createElement('span');r.className='ripple';
    const rect=btn.getBoundingClientRect();
    r.style.left=(e.clientX-rect.left-10)+'px';r.style.top=(e.clientY-rect.top-10)+'px';
    btn.appendChild(r);setTimeout(()=>r.remove(),700);
    if(e.currentTarget.id!=='btn-main')e.currentTarget.textContent='Clicked!';
  }});
}});
</script>
</body>
</html>
"""


def escape_xml(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "GenerateUI",
    "escape_xml",
]
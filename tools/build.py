#!/usr/bin/env python3
import csv
import html
import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
CONTENT_DIR = BASE_DIR / "content"
SITE_DIR = BASE_DIR / "site"
MEDIA_DIR = CONTENT_DIR / "media"
ASSETS_DIR = SITE_DIR / "assets" / "img"
BLOCKS_DIR = CONTENT_DIR / "blocks"
DIGESTS_DIR = CONTENT_DIR / "digests"
CONTROL_CSV = CONTENT_DIR / "control.csv"

INTRO_KEY = "he_intro_seen"
THEME_KEY = "he_theme"


def _escape(text: str) -> str:
    return html.escape(text or "", quote=True)


def _normalize_slug(raw: str) -> str:
    slug = (raw or "").strip()
    if slug in {"", "/", "index", "/index/"}:
        return "/"
    if not slug.startswith("/"):
        slug = f"/{slug}"
    if not slug.endswith("/"):
        slug = f"{slug}/"
    return slug


def _slug_dir(slug: str) -> str:
    normalized = _normalize_slug(slug)
    if normalized == "/":
        return ""
    return normalized.strip("/")


def _rel_link(current_slug: str, target_slug: str) -> str:
    current_dir = _slug_dir(current_slug) or "."
    target_dir = _slug_dir(target_slug) or "."
    rel = os.path.relpath(target_dir, start=current_dir)
    if rel == ".":
        return "./"
    return rel.rstrip("/") + "/"


def _resolve_internal_url(raw_url: str, current_slug: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("http") or raw_url.startswith("mailto:") or raw_url.startswith("#"):
        return raw_url
    target = raw_url
    if not raw_url.startswith("/"):
        target = f"/{raw_url.strip('/')}/"
    return _rel_link(current_slug, target)


def _render_inline_markdown(text: str) -> str:
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    parts: list[str] = []
    last = 0
    for match in pattern.finditer(text or ""):
        parts.append(_escape((text or "")[last:match.start()]))
        label = _escape(match.group(1))
        href = _escape(match.group(2))
        parts.append(f"<a href=\"{href}\">{label}</a>")
        last = match.end()
    parts.append(_escape((text or "")[last:]))
    return "".join(parts)


def _render_markdown(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return ""
    blocks = re.split(r"\n\s*\n", cleaned)
    rendered: list[str] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if all(line.lstrip().startswith(("-", "*")) for line in lines):
            items = [
                f"<li>{_render_inline_markdown(line.lstrip()[1:].strip())}</li>"
                for line in lines
            ]
            rendered.append("<ul>" + "".join(items) + "</ul>")
            continue
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", lines[0])
        if heading_match:
            level = len(heading_match.group(1))
            heading = _render_inline_markdown(heading_match.group(2))
            tag = "h2" if level == 1 else "h3" if level == 2 else "h4"
            rendered.append(f"<{tag}>{heading}</{tag}>")
            rest = [line for line in lines[1:] if line.strip()]
            if rest:
                rendered.append(f"<p>{_render_inline_markdown(' '.join(rest))}</p>")
            continue
        rendered.append(f"<p>{_render_inline_markdown(' '.join(lines))}</p>")
    return "\n".join(rendered)


def _resolve_block_path(source_md: str) -> Path | None:
    if not source_md:
        return None
    source = Path(source_md)
    if source.is_absolute():
        candidate = source
    elif "/" in source_md or "\\" in source_md:
        candidate = CONTENT_DIR / source
    else:
        candidate = BLOCKS_DIR / source
    resolved = candidate.resolve()
    if not resolved.is_relative_to(CONTENT_DIR):
        raise ValueError(f"Block path outside content directory: {source_md}")
    return resolved


def _read_block(source_md: str) -> str:
    path = _resolve_block_path(source_md)
    if not path:
        return ""
    if not path.exists():
        raise ValueError(f"Missing block file: {path}")
    return path.read_text(encoding="utf-8")


def _rel_asset_path(current_slug: str, asset_path: str) -> str:
    current_dir = _slug_dir(current_slug) or "."
    target = asset_path.lstrip("/")
    rel = os.path.relpath(target, start=current_dir)
    return rel


def _rel_root_path(current_slug: str, target_path: str) -> str:
    return _rel_asset_path(current_slug, target_path)


def _resolve_image_ref(image_ref: str, current_slug: str) -> str:
    image = (image_ref or "").strip()
    if not image:
        return ""
    if image.startswith("assets/"):
        return _rel_asset_path(current_slug, image)
    return _rel_asset_path(current_slug, f"assets/img/{image}")


def read_site_config():
    path = CONTENT_DIR / "site.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def copy_assets():
    if not MEDIA_DIR.exists():
        return
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for item in MEDIA_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, ASSETS_DIR / item.name)


def read_control():
    if not CONTROL_CSV.exists():
        raise ValueError(f"Missing control file: {CONTROL_CSV}")
    pages: dict[str, dict[str, object]] = {}
    with CONTROL_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {k: (v or "").strip() for k, v in raw.items()}
            status = (row.get("status") or "").lower()
            if status in {"draft", "hidden", "archived", "inactive"}:
                continue
            slug = _normalize_slug(row.get("page_slug", ""))
            order = int(row.get("order") or 0)
            page = pages.setdefault(slug, {"title": slug.strip("/").title() or "Home", "sections": [], "order": 0})
            kind = (row.get("kind") or "section").lower()
            if kind in {"page", "meta"}:
                if row.get("title"):
                    page["title"] = row["title"]
                page["order"] = order
                continue
            section_id = row.get("section") or row.get("id") or ""
            page["sections"].append({
                "id": row.get("id", ""),
                "section_id": section_id,
                "title": row.get("title", ""),
                "source_md": row.get("source_md", ""),
                "hero_image": row.get("hero_image", ""),
                "cta_text": row.get("cta_text", ""),
                "cta_url": row.get("cta_url", ""),
                "kind": kind,
                "order": order,
            })
    for page in pages.values():
        page["sections"].sort(key=lambda s: s["order"])
    return pages


def read_links():
    path = CONTENT_DIR / "links.csv"
    links = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {k: (v or "").strip() for k, v in raw.items()}
            links.append({
                "label": row["label"],
                "url": row["url"],
                "icon": row["icon"],
                "order": int(row["order"] or 0),
            })
    links.sort(key=lambda l: l["order"])
    return links


def read_digests():
    index_path = DIGESTS_DIR / "index.json"
    if not index_path.exists():
        return []
    raw = json.loads(index_path.read_text(encoding="utf-8"))
    items = []
    for entry in raw.get("digests", []):
        if not isinstance(entry, dict):
            continue
        date = str(entry.get("date", "")).strip()
        title = str(entry.get("title", "")).strip()
        slug = str(entry.get("slug", "")).strip()
        source_md = str(entry.get("source_md", "")).strip()
        if not (date and slug and source_md):
            continue
        items.append({
            "date": date,
            "title": title or f"Digest {date}",
            "slug": slug,
            "source_md": source_md,
        })
    return items


def parse_frontmatter(raw: str, filepath: Path) -> tuple[dict[str, str], str]:
    """
    Parse YAML-style frontmatter from markdown content.
    
    Returns:
        tuple: (metadata dict, body content)
    
    Raises:
        ValueError: If frontmatter is malformed
    """
    if not raw.startswith("---"):
        return {}, raw
    
    parts = re.split(r"^---\s*$", raw, maxsplit=2, flags=re.MULTILINE)
    
    if len(parts) < 3:
        raise ValueError(
            f"Malformed frontmatter in {filepath.name}: "
            f"Missing closing '---' separator. "
            f"Frontmatter must be enclosed between two '---' lines."
        )
    
    frontmatter_block = parts[1].strip()
    body = parts[2].strip()
    
    if not frontmatter_block:
        raise ValueError(
            f"Empty frontmatter in {filepath.name}: "
            f"Frontmatter block exists but contains no data."
        )
    
    metadata = {}
    for line_num, line in enumerate(frontmatter_block.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if ":" not in line:
            raise ValueError(
                f"Invalid frontmatter syntax in {filepath.name} at line {line_num}: "
                f"Expected 'key: value' format, got '{line}'"
            )
        
        key, value = line.split(":", 1)
        k = key.strip().lower()
        v = value.strip().strip('"').strip("'")
        
        if not k:
            raise ValueError(
                f"Empty key in frontmatter in {filepath.name} at line {line_num}"
            )
        
        metadata[k] = v
    
    return metadata, body


def parse_blog_post(path: Path):
    raw = path.read_text(encoding="utf-8")
    title = ""
    date_value = ""
    body = ""
    slug = path.stem
    match = re.match(r"\d{4}-\d{2}-\d{2}-(.+)", slug)
    if match:
        slug = match.group(1)

    # Try YAML frontmatter first
    try:
        metadata, body = parse_frontmatter(raw, path)
        if metadata:
            title = metadata.get("title", "")
            date_value = metadata.get("date", "")
            slug = metadata.get("slug", slug)
            
            if not date_value:
                date_value = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
            
            return {
                "title": title or path.stem,
                "date": date_value,
                "body": body,
                "slug": slug,
                "filename": path.name,
            }
    except ValueError as e:
        print(f"[WARNING] Frontmatter parsing failed for {path.name}: {e}")
        print(f"[WARNING] Falling back to legacy format for {path.name}")

    # Legacy format fallback
    body_lines = []
    mode = None
    lines = raw.splitlines()
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("Title:"):
            title = stripped.replace("Title:", "", 1).strip()
            mode = None
        elif stripped.startswith("Date:"):
            date_value = stripped.replace("Date:", "", 1).strip()
            mode = None
        elif stripped.startswith("Body:"):
            mode = "body"
        elif mode == "body":
            body_lines.append(stripped)
    
    body = "\n".join(body_lines).strip()
    if not title:
        title = path.stem
    if not date_value:
        date_value = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")

    return {
        "title": title,
        "date": date_value,
        "body": body,
        "slug": slug,
        "filename": path.name,
    }


def read_blog_posts():
    posts = []
    blog_dir = CONTENT_DIR / "blog"
    if not blog_dir.exists():
        return posts
    for path in sorted(blog_dir.glob("*.txt")):
        posts.append(parse_blog_post(path))
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_nav(pages, current_slug: str):
    entries = []
    for slug, page in pages.items():
        if slug in ("/privacy/", "/imprint/", "/legal/"):
            continue
        depth = len(_slug_dir(slug).split("/")) if _slug_dir(slug) else 0
        if depth > 1:
            continue
        entries.append({"slug": slug, "title": page["title"], "order": page.get("order", 0)})
    entries.sort(key=lambda e: e["order"])
    return "\n".join(
        f"<a href=\"{_rel_link(current_slug, slug)}\">{title}</a>"
        for slug, title in ((e["slug"], e["title"]) for e in entries)
    )


def render_head(site, page_title, current_slug="/"):
    title = f"{page_title} | {site['site_title']}"
    meta_description = site.get("meta_description", "")
    css_path = _rel_asset_path(current_slug, "assets/css/holobiontic.css")
    return f"""
<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
  <meta name="description" content="{meta_description}" />
  <title>{title}</title>
  <link rel="stylesheet" href="{css_path}">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&family=Outfit:wght@200;300;400;500&display=swap');

    :root {{
      --bg-dark: #050505;
      --bg-light: #f4f1ee;
      --text-light: #ececec;
      --text-dark: #1b1b1b;
      --accent: {site['accent']};
      --muted: #888888;
      --card: rgba(20, 20, 24, 0.65);
      --card-border: rgba(255, 255, 255, 0.08);
      --glass: rgba(20, 20, 24, 0.4);
      --glass-light: rgba(255, 255, 255, 0.6);
      --shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.5);
      --radius: 20px;
      --font-body: "Outfit", sans-serif;
      --font-display: "Cormorant Garamond", serif;
      --ease: cubic-bezier(0.2, 0.0, 0.2, 1);
    }}

    [data-theme="light"] {{
      --bg-dark: #f4f1ee;
      --text-light: #1b1b1b;
      --card: rgba(255, 255, 255, 0.7);
      --card-border: rgba(0, 0, 0, 0.06);
      --glass: rgba(255, 255, 255, 0.45);
      --muted: #666;
      --shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.08);
      --text-dark: #ececec; 
    }}

    * {{ box-sizing: border-box; }}
    
    body {{
      margin: 0;
      font-family: var(--font-body);
      background: radial-gradient(circle at 50% 0%, #1a1a20 0%, #050505 70%);
      color: var(--text-light);
      min-height: 100vh;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }}

    [data-theme="light"] body {{
      background: radial-gradient(circle at 50% 0%, #ffffff 0%, #ebe6e1 100%);
      color: var(--text-light);
    }}

    a {{ color: inherit; text-decoration: none; transition: color 0.2s; }}
    a:hover {{ color: var(--accent); }}

    .frame {{
      min-height: 100vh;
      padding: 100px 6vw 80px;
      position: relative;
    }}

    .noise {{
      position: fixed;
      inset: 0;
      background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/></filter><rect width="200" height="200" filter="url(%23n)" opacity="0.04"/></svg>');
      pointer-events: none;
      mix-blend-mode: overlay;
      z-index: 0;
    }}

    header {{
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      background: rgba(5, 5, 5, 0.75);
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      transition: background 0.3s, border-color 0.3s;
    }}

    [data-theme="light"] header {{
      background: rgba(244, 241, 238, 0.85);
      border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    }}

    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 6vw;
    }}

    .nav-title {{
      font-family: var(--font-display);
      font-size: 1.3rem;
      letter-spacing: 0.5px;
      font-weight: 600;
      text-transform: uppercase;
    }}

    .logo-group {{
      position: relative;
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .logo-group:hover .nav-links-wrapper {{
      opacity: 1;
      visibility: visible;
      transform: translateY(0);
      pointer-events: auto;
    }}
    .nav-links-wrapper {{
      position: absolute;
      top: 100%;
      left: -12px;
      padding-top: 20px;
      opacity: 0;
      visibility: hidden;
      transform: translateY(-8px);
      transition: all 0.2s var(--ease);
      pointer-events: none;
    }}
    .nav-links {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: var(--bg-dark);
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 16px 20px;
      border-radius: 12px;
      min-width: 220px;
      box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }}

    .toggle {{
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: transparent;
      color: inherit;
      padding: 8px 16px;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 1px;
      transition: all 0.2s;
    }}

    .toggle:hover {{
      background: rgba(255, 255, 255, 0.1);
    }}

    .hero {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 60px;
      padding: 60px 0 40px;
      position: relative;
      align-items: center;
    }}

    .hero h1 {{
      font-family: var(--font-display);
      font-size: clamp(3rem, 6vw, 5.5rem);
      margin: 0 0 24px;
      line-height: 1;
      letter-spacing: -0.02em;
    }}

    .hero p {{ 
      font-size: 1.15rem; 
      line-height: 1.7; 
      color: var(--muted);
      max-width: 540px;
    }}

    .accent {{ color: var(--accent); }}

    .cta {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 16px 32px;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      font-size: 0.85rem;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 500;
      box-shadow: 0 12px 24px rgba(107, 15, 26, 0.25);
      transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease);
    }}

    .cta:hover {{
      transform: translateY(-2px);
      box-shadow: 0 16px 32px rgba(107, 15, 26, 0.35);
    }}

    section {{
      margin-top: 60px;
      padding: 40px;
      border-radius: var(--radius);
      background: var(--card);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      box-shadow: var(--shadow);
    }}

    section h2 {{
      font-family: var(--font-display);
      margin-top: 0;
      font-size: 2rem;
      letter-spacing: 1px;
      margin-bottom: 24px;
    }}

    .grid, .tile-grid, .profile-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      margin-top: 32px;
    }}

    .card, .tile-card {{
      padding: 24px;
      border-radius: var(--radius);
      background: var(--card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
    }}

    .card:hover, .tile-card:hover {{
      transform: translateY(-6px);
      box-shadow: 0 30px 60px -10px rgba(0,0,0,0.4); 
      border-color: rgba(255,255,255,0.2);
    }}
    
    [data-theme="light"] .card:hover {{
       box-shadow: 0 30px 60px -10px rgba(0,0,0,0.1); 
       border-color: rgba(0,0,0,0.15);
    }}

    .tile-media img {{
      width: 100%;
      border-radius: calc(var(--radius) - 4px);
      border: 1px solid var(--card-border);
      display: block;
      margin-bottom: 16px;
    }}

    .tile-card h3 {{
      margin: 0 0 8px;
      font-family: var(--font-display);
      font-size: 1.2rem;
    }}

    .tile-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .profile-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 18px;
    }}
    .profile-card h3 {{
      margin-top: 0;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .newsletter-form,
    .contact-form {{
      display: grid;
      gap: 12px;
    }}
    .newsletter-form input,
    .contact-form input,
    .contact-form textarea {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      background: transparent;
      color: inherit;
      font-family: var(--font-body);
    }}
    .newsletter-form label,
    .contact-form label {{
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    [data-theme=\"light\"] .newsletter-form input,
    [data-theme=\"light\"] .contact-form input,
    [data-theme=\"light\"] .contact-form textarea {{
      border: 1px solid rgba(0, 0, 0, 0.2);
    }}
    .form-status {{
      font-size: 0.9rem;
      color: var(--muted);
    }}
    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }}
    .footer {{
      margin-top: 60px;
      padding-top: 24px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 0.9rem;
      color: var(--muted);
    }}
    .intro-overlay {{
      position: fixed;
      inset: 0;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at top, rgba(19, 19, 24, 0.96) 0%, rgba(6, 6, 8, 0.98) 60%);
      z-index: 50;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.6s ease;
    }}
    .intro-overlay.active {{ opacity: 1; pointer-events: auto; }}
    .intro-card {{
      text-align: center;
      padding: 48px;
      border-radius: 26px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: rgba(10, 10, 12, 0.9);
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}
    .intro-card::before {{
      content: "";
      position: absolute;
      inset: -40%;
      background: conic-gradient(from 120deg, rgba(107, 15, 26, 0.6), transparent, rgba(107, 15, 26, 0.6));
      animation: spin 6s linear infinite;
      opacity: 0.7;
    }}
    .intro-card > * {{ position: relative; z-index: 1; }}
    .intro-actions {{
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 20px;
    }}
    .intro-skip {{
      border: 1px solid rgba(255, 255, 255, 0.2);
      padding: 10px 18px;
      border-radius: 999px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: 1px;
      font-size: 0.8rem;
    }}
    @keyframes spin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
    .fade-in {{
      animation: fadeInUp 0.8s ease both;
    }}
    @keyframes fadeInUp {{
      from {{ transform: translateY(16px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
    @media (max-width: 720px) {{
      .nav {{ flex-direction: column; align-items: flex-start; }}
      .nav-links {{ font-size: 0.8rem; }}
      section {{ padding: 20px; }}
      .intro-card {{ padding: 32px; }}
    }}
  </style>
</head>
"""


def render_footer(site):
    year = datetime.now(timezone.utc).year
    return f"""
<footer class=\"footer\">
  <div>© {year} {site['site_name']} — {site.get('footer_text', site['tagline'])}</div>
</footer>
"""


def render_header(site, nav_html):
    return f"""
<header>
  <div class=\"nav\">
    <div class=\"logo-group\">
      <div class=\"nav-title\">{site['site_title']}</div>
      <div class=\"nav-links-wrapper\">
        <nav class=\"nav-links\">{nav_html}</nav>
      </div>
    </div>
    <button class=\"toggle\" id=\"theme-toggle\">Light/Dark</button>
  </div>
</header>
"""


def render_newsletter_form(current_slug: str):
    action = _rel_root_path(current_slug, "subscribe.php")
    return f"""
<form class=\"newsletter-form\" data-newsletter-form action=\"{action}\" method=\"post\">
  <label for=\"newsletter-email\">Email</label>
  <input id=\"newsletter-email\" name=\"email\" type=\"email\" required placeholder=\"you@example.org\" />
  <div class=\"sr-only\" aria-hidden=\"true\">
    <label for=\"newsletter-company\">Company</label>
    <input id=\"newsletter-company\" name=\"company\" type=\"text\" tabindex=\"-1\" autocomplete=\"off\" />
  </div>
  <button class=\"cta\" type=\"submit\">Subscribe</button>
  <p class=\"form-status\" aria-live=\"polite\"></p>
</form>
"""


def render_contact_form(current_slug: str):
    action = _rel_root_path(current_slug, "contact.php")
    return f"""
<form class=\"contact-form\" data-contact-form action=\"{action}\" method=\"post\">
  <label for=\"contact-name\">Name</label>
  <input id=\"contact-name\" name=\"name\" type=\"text\" required />
  <label for=\"contact-email\">Email</label>
  <input id=\"contact-email\" name=\"email\" type=\"email\" required />
  <label for=\"contact-message\">Message</label>
  <textarea id=\"contact-message\" name=\"message\" rows=\"5\" required></textarea>
  <div class=\"sr-only\" aria-hidden=\"true\">
    <label for=\"contact-company\">Company</label>
    <input id=\"contact-company\" name=\"company\" type=\"text\" tabindex=\"-1\" autocomplete=\"off\" />
  </div>
  <button class=\"cta\" type=\"submit\">Send message</button>
  <p class=\"form-status\" aria-live=\"polite\"></p>
</form>
"""


def render_digest_list(digests, current_slug: str, limit=None):
    items = digests if limit is None else digests[:limit]
    if not items:
        return "<p>No digests yet. Run tools/fetch_digest.py to publish the first issue.</p>"
    cards = []
    for digest in items:
        href = _rel_link(current_slug, f"/digest/{digest['slug']}/")
        cards.append(
            f"<div class=\"card\"><div class=\"accent\">{_escape(digest['date'])}</div>"
            f"<h3><a href=\"{_escape(href)}\">{_escape(digest['title'])}</a></h3></div>"
        )
    return "<div class=\"grid\">{}</div>".format("".join(cards))


def parse_research_tiles(source_md: str):
    raw = _read_block(source_md)
    # Detect JSON
    if raw.strip().startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass # Fallback to pipe parsing if fails
            
    tiles = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [part.strip() for part in stripped.split("|")]
        if len(parts) < 4:
            raise ValueError(f"Invalid research tile line: {line}")
        title, summary, image, link = parts[:4]
        if not (title and summary and image and link):
            raise ValueError(f"Research tiles require title, summary, image, link: {line}")
        tiles.append(
            {
                "title": title,
                "summary": summary,
                "image": image,
                "link": link,
            }
        )
    return tiles


def render_research_tiles(section, current_slug: str):
    tiles = parse_research_tiles(section.get("source_md", ""))
    if not tiles:
        return ""
    cards = []
    for tile in tiles:
        # Robust field access for varying schemas (JSON vs Pipe)
        link = tile.get("link") or tile.get("url") or "#"
        href = _resolve_internal_url(link, current_slug) or "#"
        
        image_ref = _resolve_image_ref(tile.get("image", ""), current_slug)
        
        raw_summary = tile.get("summary") or tile.get("teaser") or tile.get("description") or ""
        summary = _render_inline_markdown(raw_summary)
        
        cards.append(
            f"<a class=\"tile-card\" href=\"{_escape(href)}\">"
            f"<div class=\"tile-media\"><img src=\"{image_ref}\" alt=\"{_escape(tile.get('title', ''))} image\" /></div>"
            f"<div><h3>{_escape(tile.get('title', ''))}</h3><p>{summary}</p></div>"
            f"</a>"
        )
    title = _escape(section.get("title", "Research tiles"))
    return f"""
<section class=\"fade-in research-tiles\">
  <h2>{title}</h2>
  <div class=\"tile-grid\">{''.join(cards)}</div>
</section>
"""

def render_profile_grid(section, current_slug: str):
    source = section.get("source_md", "")
    try:
        data = json.loads(_read_block(source))
    except (ValueError, FileNotFoundError):
        return ""
        
    cards = []
    for person in data:
        image_ref = _resolve_image_ref(person.get("image", ""), current_slug)
        cards.append(
            f"<div class=\"card profile-card\">"
            f"<div class=\"profile-media\"><img src=\"{image_ref}\" alt=\"{_escape(person.get('name', ''))}\" /></div>"
            f"<div><h3>{_escape(person.get('name', ''))}</h3>"
            f"<div class=\"accent\">{_escape(person.get('role', ''))}</div>"
            f"<p>{_escape(person.get('bio', ''))}</p></div>"
            f"</div>"
        )
    heading = _escape(section.get("title", "Team"))
    return f"""
<section class=\"fade-in\">
  <h2>{heading}</h2>
  <div class=\"grid profile-grid\">{''.join(cards)}</div>
</section>
"""

def render_publication_list(section, current_slug: str):
    source = section.get("source_md", "")
    try:
        data = json.loads(_read_block(source))
    except (ValueError, FileNotFoundError):
        return ""

    rows = []
    for pub in data:
        link = pub.get("link", "#")
        rows.append(
            f"<div class=\"pub-row\">"
            f"<div><strong><a href=\"{_escape(link)}\">{_escape(pub.get('title', ''))}</a></strong></div>"
            f"<div>{_escape(pub.get('authors', ''))}</div>"
            f"<div class=\"accent\">{_escape(pub.get('venue', ''))}, {pub.get('year', '')}</div>"
            f"</div>"
        )
    heading = _escape(section.get("title", "Publications"))
    return f"""
<section class=\"fade-in\">
  <h2>{heading}</h2>
  <div class=\"publication-list\">{''.join(rows)}</div>
</section>
"""

def render_section_block(section, current_slug: str):
    heading = _escape(section.get("title", ""))
    body_html = _render_markdown(_read_block(section.get("source_md", "")))
    cta = ""
    cta_text = section.get("cta_text") or ""
    cta_url = _resolve_internal_url(section.get("cta_url", ""), current_slug)
    if cta_text and cta_url:
        cta = f"<div style=\"margin-top: 16px;\"><a class=\"cta\" href=\"{_escape(cta_url)}\">{_escape(cta_text)}</a></div>"
    hero = ""
    image_ref = _resolve_image_ref(section.get("hero_image", ""), current_slug)
    if image_ref:
        if any(image_ref.lower().endswith(ext) for ext in [".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            hero = f"<div class=\"media\"><img src=\"{image_ref}\" alt=\"{heading} visual\" /></div>"
        else:
            hero = f"<div class=\"placeholder-image\">Image placeholder — {_escape(section.get('hero_image', ''))}</div>"
    return f"""
<section class=\"fade-in\">
  <h2>{heading}</h2>
  {body_html}
  {cta}
  {hero}
</section>
"""


def render_sections(sections, current_slug: str, digests=None, digest_limit=None, links=None):
    blocks = []
    digests = digests or []
    for section in sections:
        kind = (section.get("kind") or "section").lower()
        if kind == "hero":
            continue
        if kind == "newsletter":
            body_html = _render_markdown(_read_block(section.get("source_md", "")))
            blocks.append(
                f"<section class=\"fade-in\"><h2>{_escape(section.get('title', 'Newsletter'))}</h2>"
                f"{body_html}{render_newsletter_form(current_slug)}</section>"
            )
            continue
        if kind == "contact_form":
            body_html = _render_markdown(_read_block(section.get("source_md", "")))
            blocks.append(
                f"<section class=\"fade-in\"><h2>{_escape(section.get('title', 'Contact'))}</h2>"
                f"{body_html}{render_contact_form(current_slug)}</section>"
            )
            continue
        if kind == "digest_list":
            digest_html = render_digest_list(digests, current_slug, digest_limit)
            blocks.append(f"<section class=\"fade-in\"><h2>{_escape(section.get('title', 'Digest'))}</h2>{digest_html}</section>")
            continue
        if kind == "research_tiles":
            blocks.append(render_research_tiles(section, current_slug))
            continue
        if kind == "profile_grid":
            blocks.append(render_profile_grid(section, current_slug))
            continue
        if kind == "publication_list":
            blocks.append(render_publication_list(section, current_slug))
            continue
        if kind == "linkhub" and links is not None:
            link_cards = "".join(
                f"<div class=\"card\"><div class=\"accent\">{_escape(link['label'])}</div>"
                f"<div><a href=\"{_escape(link['url'])}\">{_escape(link['url'])}</a></div></div>"
                for link in links
            )
            blocks.append(
                f"<section class=\"fade-in\"><h2>{_escape(section.get('title', 'Links'))}</h2>"
                f"{_render_markdown(_read_block(section.get('source_md', '')))}"
                f"<div class=\"grid\">{link_cards}</div></section>"
            )
            continue
        blocks.append(render_section_block(section, current_slug))
    return "\n".join(blocks)


def render_scripts():
    return f"""
<script>
  const introKey = "{INTRO_KEY}";
  const themeKey = "{THEME_KEY}";
  const overlay = document.getElementById("intro-overlay");
  const enterBtn = document.getElementById("intro-enter");
  const skipBtn = document.getElementById("intro-skip");
  const themeToggle = document.getElementById("theme-toggle");

  function setTheme(theme) {{
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(themeKey, theme);
  }}

  function setupIntro() {{
    if (!overlay) return;
    function hideIntro() {{
      if (!overlay.classList.contains("active")) return;
      overlay.classList.remove("active");
      localStorage.setItem(introKey, "1");
    }}
    function showIntroOnce() {{
      if (localStorage.getItem(introKey)) return;
      overlay.classList.add("active");
      setTimeout(hideIntro, 2600);
    }}
    showIntroOnce();
    if (enterBtn) enterBtn.addEventListener("click", hideIntro);
    if (skipBtn) skipBtn.addEventListener("click", hideIntro);
  }}

  function createMailtoFallback(email, subject, body, container) {{
    const existing = container.querySelector('.mailto-fallback');
    if (existing) existing.remove();
    
    const link = document.createElement('a');
    link.className = 'mailto-fallback cta';
    link.style.marginTop = '10px';
    link.style.display = 'inline-block';
    link.style.background = 'transparent';
    link.style.border = '1px solid var(--accent)';
    link.style.color = 'var(--accent)';
    link.href = `mailto:${{email}}?subject=${{encodeURIComponent(subject)}}&body=${{encodeURIComponent(body)}}`;
    link.textContent = 'Send via Email App';
    container.appendChild(link);
  }}

  function setupNewsletter() {{
    const form = document.querySelector('[data-newsletter-form]');
    if (!form) return;
    
    const status = form.querySelector('.form-status');
    const emailInput = form.querySelector('input[name="email"]');
    const storageKey = 'patrick_newsletter_draft';

    // Restore draft
    const saved = localStorage.getItem(storageKey);
    if (saved && emailInput) emailInput.value = saved;

    // Save draft
    if (emailInput) {{
      emailInput.addEventListener('input', () => {{
        localStorage.setItem(storageKey, emailInput.value);
      }});
    }}

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      
      const email = emailInput ? emailInput.value.trim() : '';
      if (!email) {{
        status.textContent = 'Please enter a valid email.';
        return;
      }}

      status.textContent = 'Submitting...';
      try {{
        const response = await fetch(form.getAttribute('action'), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
          body: new URLSearchParams({{ email, company: form.querySelector('input[name="company"]')?.value || '' }})
        }});
        
        const payload = await response.json().catch(() => ({{}}));
        
        if (response.ok && payload.ok) {{
          status.textContent = 'Thanks for subscribing.';
          form.reset();
          localStorage.removeItem(storageKey);
          const fallback = form.querySelector('.mailto-fallback');
          if (fallback) fallback.remove();
        }} else {{
          throw new Error(payload.error || 'Subscription failed');
        }}
      }} catch (error) {{
        status.textContent = 'Connection failed. Please use the fallback button below.';
        console.error(error);
        createMailtoFallback('patrick.schimpl@univie.ac.at', 'Newsletter Subscription', `Please subscribe me: ${{email}}`, form);
      }}
    }});
  }}

  function setupContact() {{
    const form = document.querySelector('[data-contact-form]');
    if (!form) return;
    
    const status = form.querySelector('.form-status');
    const nameInput = form.querySelector('input[name="name"]');
    const emailInput = form.querySelector('input[name="email"]');
    const messageInput = form.querySelector('textarea[name="message"]');
    const storageKey = 'patrick_contact_draft';

    // Restore draft
    try {{
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
      if (saved.name && nameInput) nameInput.value = saved.name;
      if (saved.email && emailInput) emailInput.value = saved.email;
      if (saved.message && messageInput) messageInput.value = saved.message;
    }} catch (e) {{}}

    // Save draft
    const save = () => {{
      localStorage.setItem(storageKey, JSON.stringify({{
        name: nameInput?.value || '',
        email: emailInput?.value || '',
        message: messageInput?.value || ''
      }}));
    }};
    
    [nameInput, emailInput, messageInput].forEach(el => el?.addEventListener('input', save));

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      
      const name = nameInput ? nameInput.value.trim() : '';
      const email = emailInput ? emailInput.value.trim() : '';
      const message = messageInput ? messageInput.value.trim() : '';
      const company = form.querySelector('input[name="company"]')?.value || '';
      
      if (!name || !email || !message) {{
        status.textContent = 'Please complete all required fields.';
        return;
      }}
      
      status.textContent = 'Sending...';
      try {{
        const response = await fetch(form.getAttribute('action'), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
          body: new URLSearchParams({{ name, email, message, company }})
        }});
        
        const payload = await response.json().catch(() => ({{}}));
        
        if (response.ok && payload.ok) {{
          status.textContent = 'Message sent. Thank you.';
          form.reset();
          localStorage.removeItem(storageKey);
          const fallback = form.querySelector('.mailto-fallback');
          if (fallback) fallback.remove();
        }} else {{
          throw new Error(payload.error || 'Message failed');
        }}
      }} catch (error) {{
        status.textContent = 'Connection failed. Please use the fallback button below.';
        console.error(error);
        const body = `Name: ${{name}}\\nEmail: ${{email}}\\n\\nMessage:\\n${{message}}`;
        createMailtoFallback('patrick.schimpl@univie.ac.at', 'Website Contact Form', body, form);
      }}
    }});
  }}

  const storedTheme = localStorage.getItem(themeKey) || 'dark';
  setTheme(storedTheme);
  if (themeToggle) {{
    themeToggle.addEventListener('click', () => {{
      const current = document.documentElement.getAttribute('data-theme');
      setTheme(current === 'dark' ? 'light' : 'dark');
    }});
  }}
  setupIntro();
  setupNewsletter();
  setupContact();
</script>
"""


def render_hub(site, pages, links, digests):
    current_slug = "/"
    nav_html = build_nav(pages, current_slug)
    hub_sections = pages["/"]["sections"]
    hero_section = next((section for section in hub_sections if section.get("kind") == "hero"), hub_sections[0] if hub_sections else {})
    hero_body = _render_markdown(_read_block(hero_section.get("source_md", "")))
    hero_cta = ""
    hero_cta_text = hero_section.get("cta_text") or ""
    hero_cta_url = _resolve_internal_url(hero_section.get("cta_url", ""), current_slug)
    if hero_cta_text and hero_cta_url:
        hero_cta = f"<a class=\"cta\" href=\"{_escape(hero_cta_url)}\">{_escape(hero_cta_text)}</a>"

    hero_img_html = ""
    image_ref = _resolve_image_ref(hero_section.get("hero_image", ""), current_slug)
    if image_ref:
        hero_img_html = f"<div class=\"media\"><img src=\"{image_ref}\" alt=\"Hero visual\" /></div>"

    layout_variant = (site.get("layout_variant") or "profile").strip().lower()
    show_digest_home = str(site.get("show_digest_home", "")).strip().lower() in {"1", "true", "yes", "on"}
    intro_overlay = str(site.get("intro_overlay", "true")).strip().lower() in {"1", "true", "yes", "on"}

    tiles_sections = [section for section in hub_sections if section.get("kind") == "research_tiles"]
    tiles_html = "".join(render_research_tiles(section, current_slug) for section in tiles_sections)

    sections = [
        section
        for section in hub_sections
        if section is not hero_section and section.get("kind") != "research_tiles"
    ]
    if not show_digest_home:
        sections = [section for section in sections if section.get("kind") != "digest_list"]
    digest_limit = 5 if show_digest_home else 0
    renderable_sections = sections
    if layout_variant == "profile":
        renderable_sections = [section for section in sections if section.get("kind") != "profile_card"]
    sections_html = render_sections(
        renderable_sections,
        current_slug,
        digests=digests,
        digest_limit=digest_limit if digest_limit else None,
        links=links,
    )

    profile_cards = [section for section in sections if section.get("kind") == "profile_card"]
    profile_cards_html = ""
    if profile_cards:
        cards = [
            f"<div class=\"card profile-card\"><h3>{_escape(section.get('title', ''))}</h3>"
            f"{_render_markdown(_read_block(section.get('source_md', '')))}</div>"
            for section in profile_cards
        ]
        profile_cards_html = f"<section class=\"fade-in\"><h2>Profile</h2><div class=\"profile-grid\">{''.join(cards)}</div></section>"

    if layout_variant == "linkhub":
        body_html = f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(site.get('intro_title', site.get('site_title', '')))} <span class=\"accent\">{_escape(site.get('intro_subtitle', ''))}</span></h1>
      {hero_body}
      <div style=\"margin-top: 18px;\">{hero_cta}</div>
    </div>
    {hero_img_html}
  </div>
  {tiles_html}
  {sections_html}
  {render_footer(site)}
</div>
"""
    elif layout_variant == "standard":
        body_html = f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(site.get('intro_title', site.get('site_title', '')))} <span class=\"accent\">{_escape(site.get('intro_subtitle', ''))}</span></h1>
      {hero_body}
      <div style=\"margin-top: 18px;\">{hero_cta}</div>
    </div>
    {hero_img_html}
  </div>
  {tiles_html}
  {sections_html}
  {render_footer(site)}
</div>
"""
    else:
        body_html = f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(site.get('intro_title', site.get('site_title', '')))} <span class=\"accent\">{_escape(site.get('intro_subtitle', ''))}</span></h1>
      {hero_body}
      <div style=\"margin-top: 18px;\">{hero_cta}</div>
    </div>
    {hero_img_html}
  </div>
  {tiles_html}
  {profile_cards_html}
  {sections_html}
  {render_footer(site)}
</div>
"""

    overlay_html = ""
    if intro_overlay:
        overlay_html = f"""
<div class=\"intro-overlay\" id=\"intro-overlay\">
  <div class=\"intro-card\">
    <div style=\"text-transform: uppercase; letter-spacing: 3px;\">{_escape(site.get('site_title', ''))}</div>
    <h2 style=\"margin: 16px 0;\">{_escape(site.get('intro_title', ''))}</h2>
    <p>Intro overlay with animated graphic. Auto-dismisses after a moment.</p>
    <div class=\"intro-actions\">
      <button class=\"cta\" id=\"intro-enter\">Enter</button>
      <button class=\"intro-skip\" id=\"intro-skip\">Skip</button>
    </div>
  </div>
</div>
"""

    parts = [
        render_head(site, pages["/"]["title"], "/"),
        "\n<body>\n<div class=\"noise\"></div>\n",
        render_header(site, nav_html),
        body_html,
        overlay_html,
        render_scripts(),
        "\n</body>\n</html>\n"
    ]
    return "".join(parts)


def render_page(site, pages, slug, links, posts, digests):
    nav_html = build_nav(pages, slug)
    page = pages[slug]
    sections = list(page["sections"])
    hero_section = next((section for section in sections if section.get("kind") == "hero"), sections[0] if sections else {})
    hero_body = _render_markdown(_read_block(hero_section.get("source_md", "")))
    hero_image = ""
    image_ref = _resolve_image_ref(hero_section.get("hero_image", ""), slug)
    if image_ref:
        hero_image = f"<div class=\"media\"><img src=\"{image_ref}\" alt=\"{_escape(page['title'])} visual\" /></div>"
    hero_cta = ""
    hero_cta_text = hero_section.get("cta_text") or ""
    hero_cta_url = _resolve_internal_url(hero_section.get("cta_url", ""), slug)
    if hero_cta_text and hero_cta_url:
        hero_cta = f"<div style=\"margin-top: 16px;\"><a class=\"cta\" href=\"{_escape(hero_cta_url)}\">{_escape(hero_cta_text)}</a></div>"

    content_sections = [section for section in sections if section is not hero_section]
    sections_html = render_sections(content_sections, slug, digests=digests, links=links)

    extras = ""
    if slug == "/blog/":
        post_cards = [
            f"<div class=\"card\"><div class=\"accent\">{_escape(post['date'])}</div>"
            f"<h3>{_escape(post['title'])}</h3>"
            f"<a href=\"{_escape(_rel_link(slug, f'/blog/{post['slug']}/'))}\">Read</a></div>"
            for post in posts
        ]
        extras = f"""
<section class=\"fade-in\">
  <h2>Posts</h2>
  <div class=\"grid\">{''.join(post_cards)}</div>
</section>
"""

    parts = [
        render_head(site, page["title"], slug),
        "\n<body>\n<div class=\"noise\"></div>\n",
        render_header(site, nav_html),
        f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(page['title'])}</h1>
      {hero_body}
      {hero_cta}
    </div>
    {hero_image}
  </div>
  {sections_html}
  {extras}
  {render_footer(site)}
</div>
{render_scripts()}
</body>
</html>
"""
    ]
    return "".join(parts)


def render_blog_post(site, pages, post):
    current_slug = f"/blog/{post['slug']}/"
    nav_html = build_nav(pages, current_slug)
    body_html = _render_markdown(post.get("body", ""))
    back_link = _rel_link(current_slug, "/blog/")
    parts = [
        render_head(site, post["title"], current_slug),
        "\n<body>\n<div class=\"noise\"></div>\n",
        render_header(site, nav_html),
        f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(post['title'])}</h1>
      <p>{_escape(post['date'])}</p>
      <div style=\"margin-top: 16px;\"><a class=\"cta\" href=\"{_escape(back_link)}\">Back to blog</a></div>
    </div>
  </div>
  <section class=\"fade-in\">
    {body_html}
  </section>
  {render_footer(site)}
</div>
{render_scripts()}
</body>
</html>
"""
    ]
    return "".join(parts)


def render_digest_page(site, pages, digest):
    current_slug = f"/digest/{digest['slug']}/"
    nav_html = build_nav(pages, current_slug)
    body_html = _render_markdown(_read_block(digest.get("source_md", "")))
    back_link = _rel_link(current_slug, "/digest/")
    parts = [
        render_head(site, digest["title"], current_slug),
        "\n<body>\n<div class=\"noise\"></div>\n",
        render_header(site, nav_html),
        f"""
<div class=\"frame\">
  <div class=\"hero fade-in\">
    <div>
      <h1>{_escape(digest['title'])}</h1>
      <p>{_escape(digest['date'])}</p>
      <div style=\"margin-top: 16px;\"><a class=\"cta\" href=\"{_escape(back_link)}\">Back to digest</a></div>
    </div>
  </div>
  <section class=\"fade-in\">
    {body_html}
  </section>
  {render_footer(site)}
</div>
{render_scripts()}
</body>
</html>
"""
    ]
    return "".join(parts)


def render_splash(site):
    root_href = _rel_link("/splash/", "/")
    return f"""
<!doctype html>
<html lang=\"en\" data-theme=\"dark\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"description\" content=\"{site.get('meta_description', '')}\" />
  <title>{site['site_title']} | Splash</title>
  <style>
    :root {{
      --accent: {site['accent']};
      --bg: {site['bg_dark']};
      --text: {site['text_light']};
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at top, #15151b 0%, #0b0b0c 50%, #050506 100%);
      color: var(--text);
      font-family: "Cormorant Garamond", "Garamond", "Georgia", serif;
    }}
    .orb {{
      width: min(60vw, 360px);
      height: min(60vw, 360px);
      border-radius: 50%;
      background: conic-gradient(from 30deg, rgba(107, 15, 26, 0.9), rgba(255, 255, 255, 0.05), rgba(107, 15, 26, 0.9));
      animation: spin 10s linear infinite;
      filter: blur(0.2px);
      box-shadow: 0 0 60px rgba(107, 15, 26, 0.4);
    }}
    .content {{
      position: absolute;
      text-align: center;
    }}
    h1 {{
      margin: 0 0 8px;
      letter-spacing: 4px;
      text-transform: uppercase;
    }}
    .enter {{
      margin-top: 16px;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 18px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      text-transform: uppercase;
      letter-spacing: 2px;
      color: inherit;
      text-decoration: none;
    }}
    @keyframes spin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class=\"orb\"></div>
  <div class=\"content\">
    <h1>{site['site_title']}</h1>
    <div>{site['intro_subtitle']}</div>
    <a class=\"enter\" href=\"{root_href}\">Enter</a>
    <div style=\"margin-top: 12px; font-size: 0.9rem;\"><a href=\"{root_href}\">Skip</a></div>
  </div>
  <script>
    setTimeout(() => {{ window.location.href = "{root_href}"; }}, 2500);
  </script>
</body>
</html>
"""


def write_subscribe_php():
    php = """<?php
header('Content-Type: application/json');

function fail($code, $error) {
  http_response_code($code);
  echo json_encode(['ok' => false, 'error' => $error]);
  exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
  fail(405, 'method_not_allowed');
}

$honeypot = trim($_POST['company'] ?? '');
if ($honeypot !== '') {
  fail(400, 'invalid_request');
}

$email = trim($_POST['email'] ?? '');
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
  fail(400, 'invalid_email');
}

$dataDir = __DIR__ . '/data';
if (!is_dir($dataDir)) {
  mkdir($dataDir, 0750, true);
}

$rateFile = $dataDir . '/ratelimit.json';
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$now = time();
$window = 3600;
$limit = 8;

$rateHandle = fopen($rateFile, 'c+');
if (!$rateHandle) {
  fail(500, 'storage_unavailable');
}
flock($rateHandle, LOCK_EX);
$contents = stream_get_contents($rateHandle);
$rateData = $contents ? json_decode($contents, true) : [];
if (!is_array($rateData)) {
  $rateData = [];
}
$entries = $rateData[$ip] ?? [];
$entries = array_values(array_filter($entries, function($ts) use ($now, $window) {
  return $ts >= ($now - $window);
}));
if (count($entries) >= $limit) {
  flock($rateHandle, LOCK_UN);
  fclose($rateHandle);
  fail(429, 'rate_limited');
}
$entries[] = $now;
$rateData[$ip] = $entries;
rewind($rateHandle);
ftruncate($rateHandle, 0);
fwrite($rateHandle, json_encode($rateData, JSON_PRETTY_PRINT));
flock($rateHandle, LOCK_UN);
fclose($rateHandle);

$file = $dataDir . '/newsletter_signups.csv';
$handle = fopen($file, 'a');
if (!$handle) {
  fail(500, 'storage_unavailable');
}
flock($handle, LOCK_EX);
fputcsv($handle, [gmdate('c'), $email, $ip]);
flock($handle, LOCK_UN);
fclose($handle);

echo json_encode(['ok' => true]);
"""
    write_file(SITE_DIR / "subscribe.php", php)


def write_contact_php():
    php = """<?php
header('Content-Type: application/json');

function fail($code, $error) {
  http_response_code($code);
  echo json_encode(['ok' => false, 'error' => $error]);
  exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
  fail(405, 'method_not_allowed');
}

$honeypot = trim($_POST['company'] ?? '');
if ($honeypot !== '') {
  fail(400, 'invalid_request');
}

$name = trim($_POST['name'] ?? '');
$email = trim($_POST['email'] ?? '');
$message = trim($_POST['message'] ?? '');

if ($name === '' || $email === '' || $message === '') {
  fail(400, 'missing_fields');
}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
  fail(400, 'invalid_email');
}
if (mb_strlen($message) > 4000) {
  fail(400, 'message_too_long');
}

$dataDir = __DIR__ . '/data';
if (!is_dir($dataDir)) {
  mkdir($dataDir, 0750, true);
}

$rateFile = $dataDir . '/ratelimit.json';
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$now = time();
$window = 3600;
$limit = 6;

$rateHandle = fopen($rateFile, 'c+');
if (!$rateHandle) {
  fail(500, 'storage_unavailable');
}
flock($rateHandle, LOCK_EX);
$contents = stream_get_contents($rateHandle);
$rateData = $contents ? json_decode($contents, true) : [];
if (!is_array($rateData)) {
  $rateData = [];
}
$entries = $rateData[$ip] ?? [];
$entries = array_values(array_filter($entries, function($ts) use ($now, $window) {
  return $ts >= ($now - $window);
}));
if (count($entries) >= $limit) {
  flock($rateHandle, LOCK_UN);
  fclose($rateHandle);
  fail(429, 'rate_limited');
}
$entries[] = $now;
$rateData[$ip] = $entries;
rewind($rateHandle);
ftruncate($rateHandle, 0);
fwrite($rateHandle, json_encode($rateData, JSON_PRETTY_PRINT));
flock($rateHandle, LOCK_UN);
fclose($rateHandle);

$file = $dataDir . '/contact_messages.csv';
$handle = fopen($file, 'a');
if (!$handle) {
  fail(500, 'storage_unavailable');
}
flock($handle, LOCK_EX);
fputcsv($handle, [gmdate('c'), $name, $email, $message, $ip]);
flock($handle, LOCK_UN);
fclose($handle);

echo json_encode(['ok' => true]);
"""
    write_file(SITE_DIR / "contact.php", php)


def write_data_protection():
    data_dir = SITE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    htaccess = """Require all denied
<FilesMatch "\\.(csv|json)$">
  Require all denied
</FilesMatch>
"""
    write_file(data_dir / ".htaccess", htaccess)


def write_site():
    site = read_site_config()
    pages = read_control()
    links = read_links()
    posts = read_blog_posts()
    digests = read_digests()

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    copy_assets()
    write_subscribe_php()
    write_contact_php()
    write_data_protection()

    write_file(SITE_DIR / "index.html", render_hub(site, pages, links, digests))
    write_file(SITE_DIR / "splash" / "index.html", render_splash(site))

    for slug in pages:
        if slug == "/":
            continue
        if not slug.startswith("/") or not slug.endswith("/"):
            raise ValueError(f"Page slug must start/end with '/': {slug}")
        path = SITE_DIR / slug.strip("/") / "index.html"
        write_file(path, render_page(site, pages, slug, links, posts, digests))

    for post in posts:
        path = SITE_DIR / "blog" / post["slug"] / "index.html"
        write_file(path, render_blog_post(site, pages, post))

    for digest in digests:
        path = SITE_DIR / "digest" / digest["slug"] / "index.html"
        write_file(path, render_digest_page(site, pages, digest))


if __name__ == "__main__":
    write_site()
    print(f"[PATRICK] Build complete. Wrote site to {SITE_DIR}")

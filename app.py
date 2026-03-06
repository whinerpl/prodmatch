import streamlit as st
import anthropic
import requests
import base64
import time
import json
import re
import pandas as pd
from io import BytesIO

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Product Scanner",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state: cache DFS task IDs per URL ──────────────────────────
# Structure: st.session_state.dfs_tasks = {url: {"task_id": str, "result": dict|None}}
if "dfs_tasks" not in st.session_state:
    st.session_state.dfs_tasks = {}

# Persist API keys — load from secrets.toml if present, else empty string
def _get_secret(key: str) -> str:
    try:
        return st.secrets[key] or ""
    except Exception:
        return ""

for _k in ("anthropic_key", "dfs_login", "dfs_password", "jina_key"):
    if _k not in st.session_state:
        st.session_state[_k] = _get_secret(_k)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Space Mono', monospace; }

h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -1px; }

.main { background-color: #0d1117; }

.stApp { background-color: #0d1117; color: #e2e8f0; }

.block-container { padding-top: 2rem; }

div[data-testid="stSidebar"] {
    background-color: #111827;
    border-right: 1px solid #1e293b;
}

.result-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 20px;
    margin: 10px 0;
}

.ean-display {
    background: #111827;
    border: 2px solid #f97316;
    border-radius: 4px;
    padding: 16px 24px;
    font-family: 'Space Mono', monospace;
    font-size: 28px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: 4px;
    display: inline-block;
    margin: 8px 0;
}

.ean-na {
    color: #334155;
    font-style: italic;
}

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 2px;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
}

.badge-high   { background: #052e16; color: #22c55e; border: 1px solid #22c55e; }
.badge-medium { background: #2d1a00; color: #f59e0b; border: 1px solid #f59e0b; }
.badge-low    { background: #2d0c0c; color: #ef4444; border: 1px solid #ef4444; }
.badge-info   { background: #0f172a; color: #60a5fa; border: 1px solid #60a5fa; }

.source-item {
    background: #0d1117;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 12px 16px;
    margin: 6px 0;
    transition: border-color 0.2s;
}
.source-item:hover { border-color: #f97316; }

.source-title { color: #e2e8f0; font-weight: 700; font-size: 13px; }
.source-url   { color: #475569; font-size: 11px; word-break: break-all; }
.source-info  { color: #94a3b8; font-size: 12px; margin-top: 4px; }

.tag { 
    font-size: 9px; letter-spacing: 3px; text-transform: uppercase; 
    color: #f97316; font-weight: 700; margin-bottom: 4px; display: block;
}

.stButton > button {
    background: #e2e8f0 !important;
    color: #0a0a0a !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 2px !important;
    padding: 12px 28px !important;
    transition: all 0.2s !important;
}
.stButton > button:hover { background: #f97316 !important; }

.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    background: #111827 !important;
    border: 1px solid #1e293b !important;
    color: #e2e8f0 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 13px !important;
}
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
    border-color: #f97316 !important;
    box-shadow: none !important;
}

.stProgress > div > div > div { background: #f97316 !important; }

div[data-testid="stExpander"] {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 4px;
}

.stDataFrame { background: #111827; }

hr { border-color: #1e293b !important; }

.metric-box {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 16px;
    text-align: center;
}
.metric-value { font-size: 24px; font-weight: 700; color: #f97316; }
.metric-label { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #64748b; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Sidebar — API Keys + Settings
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Konfiguracja")
    st.markdown("---")

    st.markdown('<span class="tag">Anthropic API</span>', unsafe_allow_html=True)
    anthropic_key = st.text_input(
        "Klucz Anthropic",
        type="password",
        placeholder="sk-ant-...",
        help="Klucz API z console.anthropic.com",
        value=st.session_state.anthropic_key,
        key="_anthropic_key_input",
    )
    if anthropic_key:
        st.session_state.anthropic_key = anthropic_key

    st.markdown("---")
    st.markdown('<span class="tag">DataForSEO API</span>', unsafe_allow_html=True)
    dfs_login = st.text_input(
        "DataForSEO Login",
        type="password",
        placeholder="twoj@email.com",
        value=st.session_state.dfs_login,
        key="_dfs_login_input",
    )
    if dfs_login:
        st.session_state.dfs_login = dfs_login

    dfs_password = st.text_input(
        "DataForSEO Password",
        type="password",
        placeholder="••••••••",
        value=st.session_state.dfs_password,
        key="_dfs_password_input",
    )
    if dfs_password:
        st.session_state.dfs_password = dfs_password

    st.markdown("---")
    st.markdown('<span class="tag">Jina Reader API</span>', unsafe_allow_html=True)
    jina_key = st.text_input(
        "Jina API Key",
        type="password",
        placeholder="jina_...",
        help="Klucz z jina.ai/dashboard — bez klucza działa ale z niskim limitem",
        value=st.session_state.jina_key,
        key="_jina_key_input",
    )
    if jina_key:
        st.session_state.jina_key = jina_key

    # Always read from session_state so values survive tab switches
    anthropic_key = st.session_state.anthropic_key
    dfs_login     = st.session_state.dfs_login
    dfs_password  = st.session_state.dfs_password
    jina_key      = st.session_state.jina_key

    # Key status indicators (2x2 grid)
    _ks_data = [(anthropic_key,"Anthropic"),(dfs_login,"DFS Login"),(dfs_password,"DFS Pass"),(jina_key,"Jina Key")]
    _ks_cols = st.columns(2)
    for _i, (_val, _lbl) in enumerate(_ks_data):
        with _ks_cols[_i % 2]:
            _bg = "#052e16" if _val else "#1a0808"
            _fg = "#22c55e" if _val else "#ef4444"
            _ic = "✓" if _val else "✗"
            st.markdown(f'<div style="font-size:9px;letter-spacing:1px;text-align:center;padding:4px;border-radius:2px;margin-bottom:2px;background:{_bg};color:{_fg};">{_ic} {_lbl}</div>', unsafe_allow_html=True)

    st.markdown('<span class="tag">Tryb wyszukiwania</span>', unsafe_allow_html=True)
    use_dataforseo = st.toggle(
        "Użyj DataForSEO Search by Image",
        value=True,
        help="Google Lens / odwrotne wyszukiwanie obrazem (endpoint: serp/google/search_by_image)"
    )
    use_claude_vision = st.toggle(
        "Użyj Claude Vision AI",
        value=True,
        help="Rozpoznaje produkt i EAN przez AI"
    )

    if use_claude_vision:
        st.markdown("---")
        st.markdown('<span class="tag">Model Claude</span>', unsafe_allow_html=True)

        claude_model = st.radio(
            "Model",
            options=["haiku", "sonnet", "opus"],
            index=0,
            format_func=lambda x: {
                "haiku":  "⚡ Haiku 3.5  — ~$0.01/zdjęcie  (zalecany)",
                "sonnet": "🔶 Sonnet 4   — ~$0.15/zdjęcie",
                "opus":   "🔴 Opus 4     — ~$1.50/zdjęcie",
            }[x],
            label_visibility="collapsed",
        )

        MODEL_MAP = {
            "haiku":  "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-6",
            "opus":   "claude-opus-4-6",
        }
        selected_model = MODEL_MAP[claude_model]

        use_web_search = st.toggle(
            "Web Search (szuka EAN w internecie)",
            value=False,
            help=(
                "Włączone: Claude przeszukuje internet → dokładniejszy EAN, "
                "ale ~10× więcej tokenów i czasu.\n"
                "Wyłączone: tylko analiza obrazu + kontekst DataForSEO → tanie i szybkie."
            ),
        )

        # Cost hint
        if use_web_search:
            st.markdown(
                '<div style="font-size:10px;color:#f59e0b;margin-top:4px;">'
                '⚠️ Web Search może zużyć 30-50k tokenów/zapytanie</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:10px;color:#22c55e;margin-top:4px;">'
                '✅ Tryb ekonomiczny — tylko vision + DataForSEO</div>',
                unsafe_allow_html=True,
            )
    else:
        selected_model = "claude-haiku-4-5-20251001"
        use_web_search = False

    st.markdown("---")
    st.markdown('<span class="tag">Ustawienia</span>', unsafe_allow_html=True)
    poll_interval = st.slider("Czas oczekiwania na DataForSEO (s)", 3, 30, 8)
    max_retries = st.slider("Maks. prób odpytywania", 3, 15, 8)

    st.markdown("---")
    st.markdown("""
    <div style="font-size:10px; color:#334155; letter-spacing:1px; line-height:1.8;">
    DataForSEO:<br>
    • Endpoint: serp/google/search_by_image<br>
    • Standard (POST → poll → GET)<br><br>
    Claude Vision:<br>
    • Haiku: tylko analiza obrazu (~$0.01)<br>
    • + Web Search: szuka EAN online (~$0.15+)<br>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom: 40px;">
    <div class="tag">◈ System identyfikacji produktów v2</div>
    <h1 style="font-size: 48px; margin: 8px 0; color: #f8fafc;">
        PRODUCT <span style="color: #f97316;">SCANNER</span>
    </h1>
    <p style="color: #64748b; font-size: 13px; margin-top: 8px; font-family: 'Space Mono', monospace;">
        Wklej URL zdjęcia → pobierz wyniki z Google Lens (DataForSEO) + analiza AI (Claude)
    </p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

def get_dfs_auth_header(login: str, password: str) -> dict:
    cred = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}


def dfs_task_post(image_url: str, login: str, password: str) -> str:
    """Submit image task to DataForSEO, return task_id. Does NOT poll."""
    headers = get_dfs_auth_header(login, password)
    post_url = "https://api.dataforseo.com/v3/serp/google/search_by_image/task_post"
    payload = [{"image_url": image_url, "language_code": "pl", "location_code": 2616}]

    resp = requests.post(post_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status_code") != 20000:
        raise Exception(f"DataForSEO POST error: {data.get('status_message', 'Unknown')}")

    task = data["tasks"][0]
    if task.get("status_code") not in (20000, 20100):
        raise Exception(f"Task rejected: {task.get('status_message', 'Unknown')}")

    return task["id"]


def dfs_task_get(task_id: str, login: str, password: str) -> dict | None:
    """Try to fetch results for task_id. Returns result dict or None if still processing."""
    headers = get_dfs_auth_header(login, password)
    get_url = f"https://api.dataforseo.com/v3/serp/google/search_by_image/task_get/advanced/{task_id}"

    resp = requests.get(get_url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status_code") != 20000:
        return None

    task_result = data["tasks"][0]
    # 20000 = done, 20100 = queued, 40601 = still processing
    if task_result.get("status_code") == 20000 and task_result.get("result"):
        return task_result["result"][0]

    return None  # still in queue


def dataforseo_search_by_image(image_url: str, login: str, password: str,
                                poll_interval: int, max_retries: int,
                                existing_task_id: str = None) -> tuple[dict, str]:
    """
    Submit (or reuse) a DataForSEO task and poll until done.
    Returns (result_dict, task_id).
    Pass existing_task_id to skip the POST and go straight to polling.
    """
    if existing_task_id:
        task_id = existing_task_id
    else:
        task_id = dfs_task_post(image_url, login, password)

    for attempt in range(max_retries):
        time.sleep(poll_interval)
        result = dfs_task_get(task_id, login, password)
        if result is not None:
            return result, task_id

    raise Exception(
        f"DataForSEO: wyniki jeszcze nie gotowe (task_id: {task_id}). "
        f"ID zostało zapamiętane — kliknij ponownie aby sprawdzić."
    )


def parse_dfs_results(result: dict) -> dict:
    """Extract useful info from DataForSEO response."""
    parsed = {
        "keyword": result.get("keyword", ""),
        "check_url": result.get("check_url", ""),
        "items": [],
        "related_searches": [],
        "visual_similar": [],
        "pages_with_image": [],
        "organic": [],          # ← NEW: organic search results
    }

    items = result.get("items", []) or []
    for item in items:
        itype = item.get("type", "")

        if itype == "search_by_image_element":
            parsed["keyword"] = item.get("title", parsed["keyword"])

        elif itype == "related_searches_element":
            parsed["related_searches"].append(item.get("title", ""))

        elif itype == "images":
            # top-level images block with sub-items list
            for img in (item.get("items") or []):
                parsed["visual_similar"].append({
                    "title": img.get("title", "") or img.get("alt", ""),
                    "url": img.get("url", ""),
                    "image_url": img.get("image_url", ""),
                    "source": img.get("source", ""),
                })

        elif itype == "images_element":
            parsed["visual_similar"].append({
                "title": item.get("title", "") or item.get("alt", ""),
                "url": item.get("url", ""),
                "image_url": item.get("image_url", ""),
                "source": item.get("source", ""),
            })

        elif itype == "related_element":
            parsed["pages_with_image"].append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "domain": item.get("domain", ""),
            })

        elif itype == "organic":
            # ← NEW: grab organic results — rich data already present
            price_data = item.get("price") or {}
            parsed["organic"].append({
                "rank":        item.get("rank_absolute", 0),
                "title":       item.get("title", ""),
                "url":         item.get("url", ""),
                "domain":      item.get("domain", ""),
                "description": item.get("description", ""),
                "highlighted": item.get("highlighted") or [],
                "price":       price_data.get("displayed_price", ""),
                "currency":    price_data.get("currency", ""),
                "crawled_title": None,   # filled later by crawl step
            })

        parsed["items"].append(item)

    return parsed


def fetch_via_jina(url: str, timeout: int = 12, lang: str = "pl", api_key: str = "") -> dict:
    """
    Fetch a URL through Jina Reader (r.jina.ai) which bypasses 403/bot blocks.
    Returns {"title": str|None, "h1": str|None, "text": str|None, "error": str|None}.
    Jina returns clean markdown — first line is usually the title, ## is H1.
    """
    out = {"title": None, "h1": None, "text": None, "error": None}
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/plain",
            "X-Return-Format": "text",
            "Accept-Language": f"{lang},{lang[:2]};q=0.9,en;q=0.8",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.get(jina_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        text = resp.text.strip()
        out["text"] = text[:3000]

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Title: Jina always puts "Title: ..." in the first few lines — use ONLY that
        for line in lines[:8]:
            if line.lower().startswith("title:"):
                out["title"] = line[6:].strip()[:300]
                break
        # Do NOT fall back to first content line — it could be nav/skip links

        # H1: Jina renders H1 as "# ..." or "## ..."
        for line in lines[:20]:
            if line.startswith("# ") or line.startswith("## "):
                out["h1"] = line.lstrip("#").strip()[:200]
                break

    except Exception as e:
        out["error"] = str(e)[:100]
    return out


def crawl_title(url: str, timeout: int = 10) -> str | None:
    """Fetch title via Jina Reader (bypasses 403). Falls back to direct request."""
    # Try Jina first
    result = fetch_via_jina(url, timeout=timeout, api_key=st.session_state.get("jina_key",""))
    if result["title"] and not result["error"]:
        return result["title"]
    # Fallback: direct HTTP
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "pl,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        resp.raise_for_status()
        m = re.search(r"<title[^>]*>([^<]{1,300})</title>", resp.text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def crawl_organic_titles(organic_items: list, max_items: int = 6) -> list:
    """Crawl the first max_items organic URLs and fill in crawled_title."""
    results = organic_items[:]
    for item in results[:max_items]:
        url = item.get("url", "")
        if url:
            item["crawled_title"] = crawl_title(url)
    return results


def haiku_suggest_product_name(organic_items: list, api_key: str,
                                dfs_keyword: str = "") -> dict:
    """
    Send organic titles + descriptions to Claude Haiku (no vision, no web search)
    and ask it to propose the best product name + extract any visible EAN.
    Very cheap: text-only, ~500 tokens.
    """
    client = anthropic.Anthropic(api_key=api_key)

    lines = []
    for i, item in enumerate(organic_items[:8], 1):
        title    = item.get("crawled_title") or item.get("title", "")
        desc     = item.get("description", "")[:150]
        domain   = item.get("domain", "")
        price    = item.get("price", "")
        lines.append(
            f"{i}. [{domain}]\n"
            f"   Tytuł: {title}\n"
            f"   Opis: {desc}"
            + (f"\n   Cena: {price}" if price else "")
        )

    context = "\n\n".join(lines)
    if dfs_keyword:
        context = f"Słowo kluczowe Google Lens: {dfs_keyword}\n\n" + context

    prompt = f"""Na podstawie poniższych wyników wyszukiwania odwrotnego obrazem (Google Lens) 
zaproponuj najlepszą nazwę produktu oraz wyciągnij wszelkie kody EAN/SKU/model jeśli widoczne w tytułach.

{context}

Odpowiedz TYLKO w formacie JSON (bez markdown):
{{
  "proposed_name": "Najlepsza propozycja pełnej nazwy produktu",
  "brand": "Marka",
  "model_number": "numer modelu lub SKU jeśli widoczny, np. A0682-0001",
  "ean": "kod EAN jeśli widoczny w tytułach/opisach, lub null",
  "confidence": "high/medium/low",
  "reasoning": "krótkie uzasadnienie wyboru nazwy"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text if response.content else ""
    try:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {"proposed_name": raw[:200], "brand": None, "model_number": None,
            "ean": None, "confidence": "low", "reasoning": ""}


def claude_analyze_product(image_source: dict, dfs_context: dict, api_key: str,
                            model: str = "claude-haiku-4-5-20251001",
                            use_web_search: bool = False) -> dict:
    """Use Claude Vision to identify product and find EAN.
    
    image_source: {"type": "url", "url": "https://..."}
               or {"type": "base64", "media_type": "image/jpeg", "data": "<b64>"}
    """
    client = anthropic.Anthropic(api_key=api_key)
    
    context_str = ""
    if dfs_context:
        keyword = dfs_context.get("keyword", "")
        related = dfs_context.get("related_searches", [])[:5]
        pages = dfs_context.get("pages_with_image", [])[:5]
        
        context_str = f"\n\nKontekst z Google Lens (DataForSEO):\n"
        if keyword:
            context_str += f"- Rozpoznane słowo kluczowe: {keyword}\n"
        if related:
            context_str += f"- Powiązane wyszukiwania: {', '.join(related)}\n"
        if pages:
            context_str += f"- Strony z tym produktem:\n"
            for p in pages:
                context_str += f"  • {p['title']} ({p['domain']}): {p['description'][:100]}\n"

    system_prompt = """Jesteś ekspertem od identyfikacji produktów konsumenckich.
Twoim zadaniem jest:
1. Rozpoznać dokładny produkt na zdjęciu (pełna nazwa handlowa, marka, wariant, pojemność/waga/rozmiar)
2. Wyszukać kod EAN/GTIN/barcode dla tego produktu
3. Zebrać wiarygodne źródła potwierdzające nazwę i EAN

Odpowiedz TYLKO w formacie JSON (bez markdown, bez ```), przykład:
{
  "product_name": "Pełna oficjalna nazwa produktu",
  "brand": "Marka",
  "variant": "Wariant/smak/kolor/rozmiar",
  "ean": "1234567890123",
  "ean_confidence": "high/medium/low/unknown",
  "confidence": "high/medium/low",
  "category": "Kategoria produktu",
  "description": "Krótki opis",
  "sources": [
    {
      "title": "Nazwa strony",
      "url": "https://...",
      "info": "Co potwierdza (nazwa, EAN, itp.)"
    }
  ],
  "search_queries": ["zapytanie 1", "zapytanie 2"]
}"""

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": image_source,
                },
                {
                    "type": "text",
                    "text": f"Zidentyfikuj ten produkt i znajdź jego dokładną nazwę handlową oraz kod EAN-13. Przeszukaj internet.{context_str}",
                },
            ],
        }
    ]

    create_kwargs = dict(
        model=model,
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    )
    if use_web_search:
        create_kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

    response = client.messages.create(**create_kwargs)

    # Extract text blocks
    full_text = ""
    for block in response.content:
        if block.type == "text":
            full_text += block.text

    # Parse JSON
    try:
        json_match = re.search(r'\{[\s\S]*\}', full_text)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return {
        "product_name": full_text[:200] if full_text else "Nie udało się rozpoznać",
        "brand": None, "variant": None, "ean": None,
        "ean_confidence": "unknown", "confidence": "low",
        "category": None, "description": None,
        "sources": [], "search_queries": []
    }


def analyze_single(image_url: str, use_dfs: bool, use_claude: bool,
                   dfs_login: str, dfs_password: str, anthropic_key: str,
                   poll_interval: int, max_retries: int,
                   uploaded_bytes: bytes = None, uploaded_mime: str = "image/jpeg",
                   claude_model: str = "claude-haiku-4-5-20251001",
                   use_web_search: bool = False) -> dict:
    """Full pipeline for a single image URL or uploaded file.

    DataForSEO task IDs are cached in st.session_state.dfs_tasks[url]
    so that re-clicking Skanuj reuses the existing task instead of POSTing again.
    """
    result = {"url": image_url or "upload", "dfs": None, "claude": None, "error": None}
    is_upload = uploaded_bytes is not None

    dfs_context = {}

    # ── DataForSEO — with task_id caching ────────────────────────────────
    if use_dfs and dfs_login and dfs_password:
        if is_upload and not image_url:
            result["dfs_error"] = "DataForSEO wymaga publicznego URL — niedostępne dla przesłanych plików."
        elif image_url:
            cache = st.session_state.dfs_tasks.get(image_url, {})
            existing_task_id = cache.get("task_id")

            # If we already have a finished result cached — use it immediately
            if cache.get("result"):
                dfs_raw = cache["result"]
                result["dfs_raw"] = dfs_raw
                result["dfs"] = parse_dfs_results(dfs_raw)
                result["dfs_from_cache"] = True
                dfs_context = result["dfs"]
                # Crawl organic titles + Haiku suggestion (skip if already cached)
                cached_organic = cache.get("organic_crawled")
                cached_haiku = cache.get("haiku_suggestion")
                if cached_organic is not None:
                    result["dfs"]["organic"] = cached_organic
                    result["haiku_suggestion"] = cached_haiku
                elif result["dfs"].get("organic") and anthropic_key:
                    result["dfs"]["organic"] = crawl_organic_titles(result["dfs"]["organic"])
                    result["haiku_suggestion"] = haiku_suggest_product_name(
                        result["dfs"]["organic"], anthropic_key,
                        dfs_keyword=result["dfs"].get("keyword", "")
                    )
                    # Save to cache
                    st.session_state.dfs_tasks[image_url]["organic_crawled"] = result["dfs"]["organic"]
                    st.session_state.dfs_tasks[image_url]["haiku_suggestion"] = result["haiku_suggestion"]
            else:
                try:
                    dfs_raw, task_id = dataforseo_search_by_image(
                        image_url, dfs_login, dfs_password, poll_interval, max_retries,
                        existing_task_id=existing_task_id,
                    )
                    # Cache the finished result
                    st.session_state.dfs_tasks[image_url] = {
                        "task_id": task_id,
                        "result": dfs_raw,
                    }
                    result["dfs_raw"] = dfs_raw
                    result["dfs"] = parse_dfs_results(dfs_raw)
                    dfs_context = result["dfs"]
                    # Crawl organic titles + Haiku product name suggestion
                    if result["dfs"].get("organic") and anthropic_key:
                        result["dfs"]["organic"] = crawl_organic_titles(result["dfs"]["organic"])
                        result["haiku_suggestion"] = haiku_suggest_product_name(
                            result["dfs"]["organic"], anthropic_key,
                            dfs_keyword=result["dfs"].get("keyword", "")
                        )
                        # Persist to cache for reuse
                        st.session_state.dfs_tasks[image_url]["organic_crawled"] = result["dfs"]["organic"]
                        st.session_state.dfs_tasks[image_url]["haiku_suggestion"] = result["haiku_suggestion"]
                except Exception as e:
                    err_msg = str(e)
                    # Even on timeout, preserve the task_id so next click reuses it
                    if existing_task_id:
                        st.session_state.dfs_tasks[image_url] = {
                            "task_id": existing_task_id,
                            "result": None,
                        }
                    elif "task_id: " in err_msg:
                        # Extract task_id from error message if POST succeeded but polling timed out
                        import re as _re
                        m = _re.search(r"task_id: ([\w-]+)", err_msg)
                        if m:
                            st.session_state.dfs_tasks[image_url] = {
                                "task_id": m.group(1),
                                "result": None,
                            }
                    result["dfs_error"] = err_msg

    # ── Claude Vision ─────────────────────────────────────────────────────
    if use_claude and anthropic_key:
        try:
            if is_upload:
                img_b64 = base64.b64encode(uploaded_bytes).decode()
                image_source = {"type": "base64", "media_type": uploaded_mime, "data": img_b64}
            else:
                image_source = {"type": "url", "url": image_url}
            result["claude"] = claude_analyze_product(
                image_source, dfs_context, anthropic_key,
                model=claude_model,
                use_web_search=use_web_search,
            )
        except Exception as e:
            result["claude_error"] = str(e)

    return result


def render_result(r: dict, idx: int = 0):
    """Render a single result card."""
    url = r.get("url", "")
    dfs = r.get("dfs")
    claude = r.get("claude")

    st.markdown(f'<div class="tag">◈ Wynik #{idx + 1}</div>', unsafe_allow_html=True)
    
    col_img, col_info = st.columns([1, 2])
    
    with col_img:
        # Show uploaded image bytes if available, else try URL
        up_bytes = r.get("_uploaded_bytes")
        up_mime  = r.get("_uploaded_mime", "image/jpeg")
        if up_bytes:
            import io
            st.image(io.BytesIO(up_bytes), use_container_width=True)
            st.markdown('<div style="font-size:10px; color:#334155;">📁 Przesłany plik</div>', unsafe_allow_html=True)
        elif url and url != "upload":
            try:
                st.image(url, use_container_width=True)
            except Exception:
                st.markdown("🖼️ Nie można załadować obrazu")
            st.markdown(f'<div style="font-size:10px; color:#334155; word-break:break-all;">{url}</div>', unsafe_allow_html=True)
        else:
            st.markdown("🖼️")

    with col_info:
        # Product name from Claude
        if claude:
            brand = claude.get("brand", "")
            name = claude.get("product_name", "—")
            variant = claude.get("variant", "")
            conf = claude.get("confidence", "low")
            cat = claude.get("category", "")
            
            badge_class = f"badge-{conf}" if conf in ("high", "medium", "low") else "badge-info"
            conf_label = {"high": "Wysoka", "medium": "Średnia", "low": "Niska"}.get(conf, conf)
            
            if brand:
                st.markdown(f'<div style="color:#f97316;font-size:11px;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px;">{brand}</div>', unsafe_allow_html=True)
            st.markdown(f'### {name}')
            if variant:
                st.markdown(f'<div style="color:#94a3b8; font-size:13px;">{variant}</div>', unsafe_allow_html=True)
            
            cols_meta = st.columns(3)
            with cols_meta[0]:
                st.markdown(f'<span class="badge {badge_class}">Pewność: {conf_label}</span>', unsafe_allow_html=True)
            if cat:
                with cols_meta[1]:
                    st.markdown(f'<span class="badge badge-info">{cat}</span>', unsafe_allow_html=True)

        elif dfs:
            keyword = dfs.get("keyword", "")
            if keyword:
                st.markdown(f'### {keyword}')
                st.markdown('<span class="badge badge-info">DataForSEO</span>', unsafe_allow_html=True)

    # ── Haiku suggestion from organic crawl ──────────────────────────────
    haiku = r.get("haiku_suggestion")
    if haiku and haiku.get("proposed_name"):
        st.markdown("---")
        hconf = haiku.get("confidence", "low")
        hbadge = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(hconf, "badge-info")
        hconf_label = {"high": "Wysoka", "medium": "Średnia", "low": "Niska"}.get(hconf, hconf)

        st.markdown(
            '<span class="tag">◈ Propozycja nazwy — Haiku (na podstawie crawlowanych tytułów)</span>',
            unsafe_allow_html=True,
        )
        col_h1, col_h2, col_h3 = st.columns([3, 1, 2])
        with col_h1:
            st.markdown(
                f'<div style="font-size:22px;font-weight:700;color:#f8fafc;font-family:Syne,sans-serif;">'
                f'{haiku["proposed_name"]}</div>',
                unsafe_allow_html=True,
            )
            if haiku.get("brand"):
                st.markdown(
                    f'<div style="font-size:12px;color:#f97316;letter-spacing:2px;margin-top:4px;">'
                    f'{haiku["brand"]}</div>',
                    unsafe_allow_html=True,
                )
        with col_h2:
            st.markdown(f'<span class="badge {hbadge}" style="margin-top:6px;display:inline-block;">Pewność: {hconf_label}</span>', unsafe_allow_html=True)
            if haiku.get("model_number"):
                st.markdown(f'<div style="font-size:10px;color:#64748b;margin-top:6px;">SKU: <code>{haiku["model_number"]}</code></div>', unsafe_allow_html=True)
        with col_h3:
            if haiku.get("ean"):
                st.markdown('<span class="tag">EAN z tytułów</span>', unsafe_allow_html=True)
                st.markdown(f'<div class="ean-display" style="font-size:18px;padding:10px 16px;">{haiku["ean"]}</div>', unsafe_allow_html=True)
        if haiku.get("reasoning"):
            st.markdown(f'<div style="font-size:11px;color:#475569;margin-top:8px;font-style:italic;">💬 {haiku["reasoning"]}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # EAN Section
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown('<span class="tag">Kod EAN</span>', unsafe_allow_html=True)
        if claude:
            ean = claude.get("ean")
            ean_conf = claude.get("ean_confidence", "unknown")
            
            if ean and ean != "null" and ean is not None:
                st.markdown(f'<div class="ean-display">{ean}</div>', unsafe_allow_html=True)
                ean_badge = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(ean_conf, "badge-info")
                label = {"high": "Potwierdzone", "medium": "Prawdopodobne", "low": "Niepewne", "unknown": "Nieznane"}.get(ean_conf, ean_conf)
                st.markdown(f'<span class="badge {ean_badge}">{label}</span>', unsafe_allow_html=True)
                if st.button(f"📋 Kopiuj EAN", key=f"copy_ean_{idx}"):
                    st.code(ean)
            else:
                st.markdown('<div class="ean-display ean-na">— nie znaleziono —</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ean-display ean-na">— brak danych AI —</div>', unsafe_allow_html=True)

    with c2:
        if dfs:
            st.markdown('<span class="tag">Google Lens — słowo kluczowe</span>', unsafe_allow_html=True)
            kw = dfs.get("keyword", "")
            if kw:
                st.markdown(f'**{kw}**')
            check = dfs.get("check_url", "")
            if check:
                st.markdown(f'[🔗 Sprawdź w Google]({check})')
            
            related = dfs.get("related_searches", [])
            if related:
                st.markdown('<span class="tag" style="margin-top:12px;">Powiązane</span>', unsafe_allow_html=True)
                for rel in related[:4]:
                    st.markdown(f'<span class="badge badge-info" style="margin:2px;">{rel}</span>', unsafe_allow_html=True)

    with c3:
        if claude and claude.get("description"):
            st.markdown('<span class="tag">Opis</span>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#94a3b8; font-size:12px; line-height:1.7;">{claude["description"]}</div>', unsafe_allow_html=True)

    # Sources tabs
    has_claude_sources = claude and claude.get("sources")
    has_dfs_pages = dfs and dfs.get("pages_with_image")
    has_organic = dfs and dfs.get("organic")

    if has_claude_sources or has_dfs_pages or has_organic:
        st.markdown("---")
        tabs = []
        if has_organic: tabs.append(f"🔍 Organic ({len(dfs['organic'])} wyników)")
        if has_claude_sources: tabs.append("🤖 Źródła AI")
        if has_dfs_pages: tabs.append("🌐 Strony Google Lens")
        if dfs and dfs.get("visual_similar"): tabs.append("🖼️ Podobne obrazy")

        tab_objects = st.tabs(tabs)
        tab_idx = 0

        # ── Organic results tab ─────────────────────────────────────────
        if has_organic:
            with tab_objects[tab_idx]:
                st.markdown(
                    '<div style="font-size:10px;color:#64748b;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">'
                    'Tytuły stron pobrane przez crawler + dane z DataForSEO</div>',
                    unsafe_allow_html=True,
                )
                for org in dfs["organic"]:
                    url_o    = org.get("url", "#")
                    domain_o = org.get("domain", "")
                    dfs_title   = org.get("title", "")
                    crawled  = org.get("crawled_title")
                    desc_o   = org.get("description", "")
                    price_o  = org.get("price", "")
                    rank_o   = org.get("rank", "")
                    highlighted = org.get("highlighted") or []

                    title_display = crawled or dfs_title or url_o
                    title_changed = crawled and crawled != dfs_title

                    st.markdown(f"""
                    <div class="source-item">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div style="flex:1;">
                                <div style="font-size:9px;color:#475569;letter-spacing:2px;margin-bottom:3px;">
                                    #{rank_o} &nbsp;·&nbsp; {domain_o}
                                    {"&nbsp;·&nbsp;<span style='color:#22c55e'>✓ tytuł crawlowany</span>" if crawled else "&nbsp;·&nbsp;<span style='color:#f59e0b'>⚠ crawl nie udał się</span>"}
                                </div>
                                <div class="source-title">
                                    <a href="{url_o}" target="_blank" style="color:#e2e8f0;text-decoration:none;">↗ {title_display[:120]}</a>
                                </div>
                                {f'<div style="font-size:10px;color:#475569;margin-top:2px;">DFS tytuł: {dfs_title[:100]}</div>' if title_changed else ""}
                                {f'<div class="source-info">{desc_o[:180]}</div>' if desc_o else ""}
                                {f'<div style="font-size:11px;color:#f97316;margin-top:4px;font-weight:700;">{price_o}</div>' if price_o else ""}
                                {f'<div style="margin-top:4px;">' + "".join(f'<span class="badge badge-info" style="margin:2px;">{h}</span>' for h in highlighted[:3]) + "</div>" if highlighted else ""}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            tab_idx += 1

        if has_claude_sources:
            with tab_objects[tab_idx]:
                for src in claude["sources"]:
                    url_s = src.get("url", "#")
                    title_s = src.get("title", url_s)
                    info_s = src.get("info", "")
                    st.markdown(f"""
                    <div class="source-item">
                        <div class="source-title">↗ <a href="{url_s}" target="_blank" style="color:#e2e8f0;text-decoration:none;">{title_s}</a></div>
                        <div class="source-url">{url_s}</div>
                        {f'<div class="source-info">{info_s}</div>' if info_s else ''}
                    </div>
                    """, unsafe_allow_html=True)
            tab_idx += 1

        if has_dfs_pages:
            with tab_objects[tab_idx]:
                for page in dfs["pages_with_image"][:10]:
                    url_p = page.get("url", "#")
                    title_p = page.get("title", url_p)
                    desc_p = page.get("description", "")
                    domain_p = page.get("domain", "")
                    st.markdown(f"""
                    <div class="source-item">
                        <div class="source-title">↗ <a href="{url_p}" target="_blank" style="color:#e2e8f0;text-decoration:none;">{title_p}</a></div>
                        <div class="source-url">{domain_p} — {url_p}</div>
                        {f'<div class="source-info">{desc_p}</div>' if desc_p else ''}
                    </div>
                    """, unsafe_allow_html=True)
            tab_idx += 1

        if dfs and dfs.get("visual_similar") and tab_idx < len(tab_objects):
            with tab_objects[tab_idx]:
                sim_cols = st.columns(4)
                for i, sim in enumerate(dfs["visual_similar"][:8]):
                    with sim_cols[i % 4]:
                        if sim.get("image_url"):
                            try:
                                st.image(sim["image_url"], use_container_width=True)
                            except Exception:
                                pass
                        st.markdown(f'<div style="font-size:10px; color:#94a3b8;">{sim.get("title","")[:40]}</div>', unsafe_allow_html=True)
                        if sim.get("url"):
                            st.markdown(f'[↗]({sim["url"]})')

    # Errors
    if r.get("dfs_error"):
        st.warning(f"⚠️ DataForSEO: {r['dfs_error']}")
    if r.get("claude_error"):
        st.warning(f"⚠️ Claude: {r['claude_error']}")

    # ── DEBUG: raw DataForSEO response ─────────────────────────────────
    st.markdown("---")
    with st.expander("🐛 Debug — surowa odpowiedź DataForSEO (kliknij aby rozwinąć)", expanded=False):
        dfs_raw = r.get("dfs_raw")
        dfs_parsed = r.get("dfs")

        from_cache = r.get("dfs_from_cache", False)
        if from_cache:
            st.success("✅ Wynik załadowany z cache session_state (bez nowego POST do DataForSEO)")

        if dfs_raw is None and dfs_parsed is None:
            st.info("Brak odpowiedzi DataForSEO (wyłączone lub błąd).")
        else:
            col_d1, col_d2 = st.columns(2)

            with col_d1:
                st.markdown("**Przetworzone (`dfs` po parse)**")
                if dfs_parsed:
                    st.markdown(f"- **keyword:** `{dfs_parsed.get('keyword','—')}`")
                    st.markdown(f"- **check_url:** {dfs_parsed.get('check_url','—')}")
                    st.markdown(f"- **related_searches:** `{dfs_parsed.get('related_searches', [])}`")
                    st.markdown(f"- **pages_with_image:** {len(dfs_parsed.get('pages_with_image',[]))} szt.")
                    st.markdown(f"- **visual_similar:** {len(dfs_parsed.get('visual_similar',[]))} szt.")
                    st.markdown(f"- **items (wszystkie):** {len(dfs_parsed.get('items',[]))} szt.")

                    if dfs_parsed.get("items"):
                        st.markdown("**Typy items:**")
                        from collections import Counter
                        types = Counter(i.get("type","?") for i in dfs_parsed["items"])
                        for t, cnt in types.items():
                            st.markdown(f"  - `{t}`: {cnt}×")
                else:
                    st.warning("dfs_parsed jest pusty/None")

            with col_d2:
                st.markdown("**Surowy JSON z API (`dfs_raw`)**")
                if dfs_raw:
                    st.json(dfs_raw)
                else:
                    st.warning("dfs_raw nie zostało zapisane")


def results_to_dataframe(results: list) -> pd.DataFrame:
    """Convert results list to exportable DataFrame."""
    rows = []
    for r in results:
        row = {"URL": r.get("url", "")}
        
        cl = r.get("claude") or {}
        row["Nazwa produktu"] = cl.get("product_name", "")
        row["Marka"] = cl.get("brand", "")
        row["Wariant"] = cl.get("variant", "")
        row["EAN"] = cl.get("ean", "")
        row["Pewność EAN"] = cl.get("ean_confidence", "")
        row["Pewność rozpoznania"] = cl.get("confidence", "")
        row["Kategoria"] = cl.get("category", "")
        row["Opis"] = cl.get("description", "")
        
        dfs = r.get("dfs") or {}
        row["Google Lens keyword"] = dfs.get("keyword", "")
        row["Google Lens URL"] = dfs.get("check_url", "")
        
        sources = cl.get("sources", [])
        row["Źródła"] = " | ".join([s.get("url", "") for s in sources[:3]])
        
        row["Błąd DFS"] = r.get("dfs_error", "")
        row["Błąd Claude"] = r.get("claude_error", "")
        
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# Main tabs
# ─────────────────────────────────────────────
tab_single, tab_bulk, tab_de = st.tabs(["🔍 Pojedyncze skanowanie", "📦 Bulk skanowanie", "🇩🇪 Weryfikacja DE"])


# ── SINGLE ──────────────────────────────────
with tab_single:
    st.markdown("### Skanuj jeden produkt")

    # Input method selector
    input_mode = st.radio(
        "Sposób podania zdjęcia:",
        ["🔗 URL zdjęcia", "📁 Prześlij plik"],
        horizontal=True,
        label_visibility="collapsed",
        key="single_input_mode",
    )

    image_url_input = ""
    uploaded_file_single = None

    if input_mode == "🔗 URL zdjęcia":
        image_url_input = st.text_input(
            "URL zdjęcia produktu",
            placeholder="https://example.com/produkt.jpg",
            label_visibility="collapsed",
        )

    else:  # Upload
        uploaded_file_single = st.file_uploader(
            "Prześlij zdjęcie produktu",
            type=["jpg", "jpeg", "png", "webp", "gif"],
            label_visibility="collapsed",
            key="uploader_single",
        )
        if uploaded_file_single:
            st.image(uploaded_file_single, width=260)
            if use_dataforseo:
                st.info(
                    "ℹ️ DataForSEO Search by Image wymaga publicznego URL — "
                    "dla przesłanych plików aktywne jest tylko Claude Vision.",
                    icon="ℹ️",
                )

    st.markdown("")  # spacer

    # ── Cache status for entered URL ───────────────────────────────────
    if image_url_input:
        cache_entry = st.session_state.dfs_tasks.get(image_url_input, {})
        if cache_entry.get("result"):
            st.markdown(
                f'<div style="font-size:11px;color:#22c55e;margin-bottom:8px;">'
                f'✅ DataForSEO: wynik z cache (task <code>{cache_entry["task_id"][:16]}…</code>)'
                f' — kliknij Skanuj aby użyć od razu</div>',
                unsafe_allow_html=True,
            )
        elif cache_entry.get("task_id"):
            st.markdown(
                f'<div style="font-size:11px;color:#f59e0b;margin-bottom:8px;">'
                f'⏳ DataForSEO: zadanie w toku (task <code>{cache_entry["task_id"][:16]}…</code>)'
                f' — kliknij Skanuj aby sprawdzić status</div>',
                unsafe_allow_html=True,
            )

    col_btn, col_clear, _ = st.columns([1, 1, 2])
    with col_btn:
        scan_btn = st.button("▶ SKANUJ", key="scan_single", use_container_width=True)
    with col_clear:
        if st.button("🗑 Wyczyść cache URL", key="clear_single_cache", use_container_width=True):
            if image_url_input and image_url_input in st.session_state.dfs_tasks:
                del st.session_state.dfs_tasks[image_url_input]
                st.success("Cache wyczyszczony — następny skan zrobi nowy POST.")

    if not use_dataforseo and not use_claude_vision:
        st.warning("⚠️ Włącz co najmniej jeden tryb wyszukiwania w panelu bocznym.")

    has_input = bool(image_url_input) or (uploaded_file_single is not None)

    if scan_btn and has_input:
        # Validate config
        errors = []
        if use_dataforseo and (not dfs_login or not dfs_password) and image_url_input:
            errors.append("Podaj login i hasło DataForSEO lub wyłącz tę opcję.")
        if use_claude_vision and not anthropic_key:
            errors.append("Podaj klucz Anthropic API lub wyłącz Claude Vision.")

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            # Prepare upload data
            up_bytes = None
            up_mime = "image/jpeg"
            if uploaded_file_single is not None:
                up_bytes = uploaded_file_single.read()
                up_mime = uploaded_file_single.type or "image/jpeg"

            with st.status("🔍 Analizowanie produktu...", expanded=True) as status:
                if use_dataforseo and image_url_input:
                    st.write("📡 Wysyłanie zapytania do DataForSEO Search by Image...")
                if use_claude_vision:
                    st.write("🤖 Claude Vision analizuje zdjęcie...")

                result = analyze_single(
                    image_url_input,
                    use_dataforseo, use_claude_vision,
                    dfs_login, dfs_password, anthropic_key,
                    poll_interval, max_retries,
                    uploaded_bytes=up_bytes,
                    uploaded_mime=up_mime,
                    claude_model=selected_model,
                    use_web_search=use_web_search,
                )
                # For display: show preview of uploaded file
                if up_bytes and not image_url_input:
                    result["_uploaded_bytes"] = up_bytes
                    result["_uploaded_mime"] = up_mime
                status.update(label="✅ Analiza zakończona!", state="complete")

            st.markdown("---")
            render_result(result, 0)

    elif scan_btn and not has_input:
        st.warning("Podaj URL lub prześlij plik zdjęcia.")


# ── BULK ─────────────────────────────────────
with tab_bulk:
    st.markdown("### Bulk skanowanie")
    st.markdown('<div style="color:#64748b; font-size:12px; margin-bottom:16px;">Wklej URLe zdjęć (jeden na linię) lub załaduj plik CSV/TXT</div>', unsafe_allow_html=True)
    
    input_method = st.radio(
        "Metoda wprowadzania:",
        ["Wklej URLe", "Plik CSV/TXT"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    urls_to_process = []
    
    if input_method == "Wklej URLe":
        bulk_text = st.text_area(
            "URLe zdjęć (jeden na linię)",
            placeholder="https://sklep.pl/produkt1.jpg\nhttps://sklep.pl/produkt2.jpg\n...",
            height=180,
            label_visibility="collapsed"
        )
        if bulk_text:
            urls_to_process = [u.strip() for u in bulk_text.splitlines() if u.strip().startswith("http")]
    else:
        uploaded = st.file_uploader("Plik CSV lub TXT", type=["csv", "txt"])
        if uploaded:
            content = uploaded.read().decode("utf-8")
            # Try CSV first
            if uploaded.name.endswith(".csv"):
                try:
                    df_upload = pd.read_csv(BytesIO(content.encode()))
                    # Find URL column
                    url_col = next((c for c in df_upload.columns if "url" in c.lower() or "link" in c.lower() or "zdjec" in c.lower()), df_upload.columns[0])
                    urls_to_process = df_upload[url_col].dropna().tolist()
                    st.success(f"✅ Załadowano {len(urls_to_process)} URLi z kolumny '{url_col}'")
                except Exception:
                    urls_to_process = [u.strip() for u in content.splitlines() if u.strip().startswith("http")]
            else:
                urls_to_process = [u.strip() for u in content.splitlines() if u.strip().startswith("http")]

    if urls_to_process:
        st.markdown(f'<span class="badge badge-info">{len(urls_to_process)} URL(i) do przetworzenia</span>', unsafe_allow_html=True)
        
        # Preview
        with st.expander("Podgląd listy URLi"):
            for i, u in enumerate(urls_to_process[:20]):
                st.markdown(f'`{i+1}.` {u}')
            if len(urls_to_process) > 20:
                st.markdown(f"... i {len(urls_to_process) - 20} więcej")

    col_bulk1, col_bulk2, col_bulk3 = st.columns([1, 1, 2])
    with col_bulk1:
        bulk_btn = st.button("▶ URUCHOM BULK", key="scan_bulk", use_container_width=True)
    with col_bulk2:
        delay_between = st.number_input("Opóźnienie między req. (s)", min_value=0.0, max_value=10.0, value=2.0, step=0.5)

    if bulk_btn and urls_to_process:
        errors = []
        if use_dataforseo and (not dfs_login or not dfs_password):
            errors.append("Podaj login i hasło DataForSEO lub wyłącz tę opcję.")
        if use_claude_vision and not anthropic_key:
            errors.append("Podaj klucz Anthropic API lub wyłącz Claude Vision.")
        if not use_dataforseo and not use_claude_vision:
            errors.append("Włącz co najmniej jeden tryb wyszukiwania.")
        
        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            bulk_results = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Summary metrics placeholders
            m1, m2, m3, m4 = st.columns(4)
            met_total = m1.empty()
            met_ok = m2.empty()
            met_ean = m3.empty()
            met_err = m4.empty()
            
            ok_count = 0
            ean_count = 0
            err_count = 0

            results_container = st.container()

            for idx, url in enumerate(urls_to_process):
                status_text.markdown(f'<span class="tag">Przetwarzanie {idx+1}/{len(urls_to_process)}: {url[:60]}...</span>', unsafe_allow_html=True)
                
                r = analyze_single(
                    url,
                    use_dataforseo, use_claude_vision,
                    dfs_login, dfs_password, anthropic_key,
                    poll_interval, max_retries,
                    claude_model=selected_model,
                    use_web_search=use_web_search,
                )
                bulk_results.append(r)
                
                # Update counters
                if not r.get("dfs_error") or not r.get("claude_error"):
                    ok_count += 1
                else:
                    err_count += 1
                
                cl = r.get("claude") or {}
                if cl.get("ean") and cl["ean"] not in (None, "null", ""):
                    ean_count += 1
                
                # Update metrics
                met_total.markdown(f'<div class="metric-box"><div class="metric-value">{idx+1}</div><div class="metric-label">Przetworzone</div></div>', unsafe_allow_html=True)
                met_ok.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#22c55e">{ok_count}</div><div class="metric-label">Sukces</div></div>', unsafe_allow_html=True)
                met_ean.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#f97316">{ean_count}</div><div class="metric-label">EAN znaleziony</div></div>', unsafe_allow_html=True)
                met_err.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#ef4444">{err_count}</div><div class="metric-label">Błędy</div></div>', unsafe_allow_html=True)
                
                progress_bar.progress((idx + 1) / len(urls_to_process))
                
                if delay_between > 0 and idx < len(urls_to_process) - 1:
                    time.sleep(delay_between)
            
            status_text.markdown('<span class="tag" style="color:#22c55e;">✅ Bulk zakończony!</span>', unsafe_allow_html=True)
            
            # Show results
            with results_container:
                st.markdown("---")
                st.markdown("### Wyniki")
                
                # Export buttons
                df_export = results_to_dataframe(bulk_results)
                
                col_ex1, col_ex2 = st.columns(2)
                with col_ex1:
                    csv_data = df_export.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        "⬇️ Pobierz CSV",
                        data=csv_data,
                        file_name="product_scan_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_ex2:
                    json_data = json.dumps(bulk_results, ensure_ascii=False, indent=2)
                    st.download_button(
                        "⬇️ Pobierz JSON",
                        data=json_data,
                        file_name="product_scan_results.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                # Table overview
                st.markdown("#### Tabela wyników")
                display_cols = ["URL", "Nazwa produktu", "Marka", "EAN", "Pewność EAN", "Google Lens keyword"]
                st.dataframe(
                    df_export[display_cols].fillna(""),
                    use_container_width=True,
                    height=300,
                )
                
                # Detailed results
                st.markdown("#### Szczegóły")
                for idx, r in enumerate(bulk_results):
                    with st.expander(f"#{idx+1} — {r.get('claude', {}).get('product_name', '') or r.get('dfs', {}).get('keyword', '') or r.get('url', '')[:60]}"):
                        render_result(r, idx)

        if bulk_btn and not urls_to_process:
            st.warning("Dodaj URLe do przetworzenia.")



# ─────────────────────────────────────────────
# German market helper functions
# ─────────────────────────────────────────────

def crawl_title_and_h1(url: str, timeout: int = 12) -> dict:
    """
    Fetch title + H1 via Jina Reader (bypasses 403/Cloudflare/bot protection).
    Falls back to direct HTTP request if Jina fails.
    """
    # Try Jina first — best for protected sites
    result = fetch_via_jina(url, timeout=timeout, lang="de", api_key=st.session_state.get("jina_key",""))
    if result["title"] and not result["error"]:
        return {
            "title": result["title"],
            "h1":    result["h1"],
            "error": None,
        }
    # Fallback: direct HTTP with DE headers
    out = {"title": None, "h1": None, "error": None}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        m_title = re.search(r"<title[^>]*>([^<]{1,400})</title>", html, re.IGNORECASE)
        if m_title:
            out["title"] = re.sub(r"\s+", " ", m_title.group(1)).strip()
        m_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if m_h1:
            raw_h1 = re.sub("<[^>]+>", "", m_h1.group(1))
            out["h1"] = re.sub(r"\s+", " ", raw_h1).strip()[:300]
    except Exception as e:
        out["error"] = str(e)[:80]
    return out


def crawl_de_organic(organic_items: list, max_items: int = 8) -> list:
    """Crawl German organic results: title + H1 for each URL."""
    results = organic_items[:]
    for item in results[:max_items]:
        url = item.get("url", "")
        if url:
            scraped = crawl_title_and_h1(url)
            item["crawled_title"] = scraped["title"]
            item["crawled_h1"]    = scraped["h1"]
            item["crawl_error"]   = scraped["error"]
        else:
            item["crawled_title"] = None
            item["crawled_h1"]    = None
            item["crawl_error"]   = "brak URL"
    return results


def claude_verify_german_name(our_name: str, organic_items: list, api_key: str,
                               model: str = "claude-haiku-4-5-20251001",
                               dfs_keyword: str = "") -> dict:
    """
    Ask Claude Haiku whether our product name is correct German
    and propose a better name if needed. Text-only, very cheap.
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Build context from crawled titles/H1s
    lines = []
    for i, item in enumerate(organic_items[:8], 1):
        domain   = item.get("domain", "")
        dfs_t    = item.get("title", "")
        crawled  = item.get("crawled_title") or ""
        h1       = item.get("crawled_h1") or ""
        desc     = item.get("description", "")[:120]
        price    = item.get("price", "")

        best_title = crawled or dfs_t
        lines.append(
            f"{i}. [{domain}]\n"
            f"   Title: {best_title}\n"
            + (f"   H1: {h1}\n" if h1 else "")
            + (f"   Opis: {desc}\n" if desc else "")
            + (f"   Cena: {price}" if price else "")
        )

    context = "\n\n".join(lines)
    kw_line = f"Słowo kluczowe Google Lens (DE): {dfs_keyword}\n\n" if dfs_keyword else ""

    prompt = f"""Sprawdzasz czy polska nazwa produktu jest poprawna na rynku niemieckim.

NASZA NAZWA PRODUKTU: "{our_name}"

{kw_line}WYNIKI WYSZUKIWANIA OBRAZEM NA RYNKU NIEMIECKIM (title + H1 stron):
{context}

Na podstawie powyższych danych z niemieckich stron odpowiedz:
1. Czy nasza nazwa jest prawidłową niemiecką nazwą tego produktu?
2. Jak ten produkt jest faktycznie nazywany na rynku DE (na podstawie title/H1)?
3. Zaproponuj optymalną nazwę dla rynku DE.

Odpowiedz TYLKO w JSON (bez markdown):
{{
  "our_name_correct": true/false,
  "our_name_assessment": "krótka ocena naszej nazwy po polsku",
  "de_product_name": "jak produkt jest nazywany na DE (z title/H1)",
  "de_name_proposed": "optymalna proponowana nazwa dla DE",
  "brand": "marka",
  "model_sku": "numer modelu/SKU jeśli widoczny",
  "ean": "kod EAN jeśli gdzieś widoczny, lub null",
  "confidence": "high/medium/low",
  "sources_used": ["domain1", "domain2"],
  "notes": "dodatkowe uwagi"
}}"""

    response = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text if response.content else ""
    try:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {
        "our_name_correct": None, "our_name_assessment": raw[:200],
        "de_product_name": None, "de_name_proposed": None,
        "brand": None, "model_sku": None, "ean": None,
        "confidence": "low", "sources_used": [], "notes": ""
    }


def dfs_search_de(image_url: str, login: str, password: str,
                   poll_interval: int, max_retries: int,
                   existing_task_id: str = None) -> tuple:
    """DataForSEO search_by_image for German market (location_code=2276, lang=de)."""
    headers = get_dfs_auth_header(login, password)

    if existing_task_id:
        task_id = existing_task_id
    else:
        post_url = "https://api.dataforseo.com/v3/serp/google/search_by_image/task_post"
        payload  = [{"image_url": image_url, "language_code": "de", "location_code": 2276}]
        resp = requests.post(post_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status_code") != 20000:
            raise Exception(f"DataForSEO POST error: {data.get('status_message')}")
        task = data["tasks"][0]
        if task.get("status_code") not in (20000, 20100):
            raise Exception(f"Task rejected: {task.get('status_message')}")
        task_id = task["id"]

    get_url = f"https://api.dataforseo.com/v3/serp/google/search_by_image/task_get/advanced/{task_id}"
    for _ in range(max_retries):
        time.sleep(poll_interval)
        resp = requests.get(get_url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status_code") != 20000:
            continue
        tr = data["tasks"][0]
        if tr.get("status_code") == 20000 and tr.get("result"):
            return tr["result"][0], task_id

    raise Exception(
        f"DataForSEO DE: wyniki jeszcze nie gotowe (task_id: {task_id}). "
        "ID zapamiętane — kliknij ponownie."
    )



# ── GERMAN MARKET ────────────────────────────
with tab_de:
    st.markdown("### 🇩🇪 Weryfikacja nazwy — rynek DE")
    st.markdown(
        '<div style="color:#64748b;font-size:12px;margin-bottom:20px;">'
        'Wklej URL grafiki produktu i naszą nazwę oddzieloną średnikiem. '
        'DataForSEO przeszuka Google DE obrazem, crawlujemy title+H1, '
        'a Haiku ocenia czy nazwa jest poprawna po niemiecku.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Input ──────────────────────────────────────────────────────────────
    de_input_mode = st.radio(
        "Tryb wprowadzania:",
        ["📋 Pojedynczy wpis", "📦 Bulk (wiele linii)"],
        horizontal=True,
        label_visibility="collapsed",
        key="de_input_mode",
    )

    de_single_input = ""
    de_bulk_lines   = []

    if de_input_mode == "📋 Pojedynczy wpis":
        de_single_input = st.text_input(
            "URL;nasza_nazwa",
            placeholder="https://example.com/product.jpg;Levi's Jeansy 501",
            label_visibility="collapsed",
            key="de_single_input",
        )
        if de_single_input and ";" not in de_single_input:
            st.warning("⚠️ Brak średnika — format: URL;nasza_nazwa_produktu")
    else:
        de_bulk_text = st.text_area(
            "Wklej wiele wpisów (jeden na linię)",
            placeholder=(
                "https://example.com/p1.jpg;Levi's Jeans 501\n"
                "https://example.com/p2.jpg;Adidas Sneaker Ultra Boost\n"
                "https://example.com/p3.jpg;Nike Air Max 90"
            ),
            height=180,
            label_visibility="collapsed",
            key="de_bulk_text",
        )
        if de_bulk_text:
            de_bulk_lines = [
                l.strip() for l in de_bulk_text.splitlines()
                if l.strip() and ";" in l
            ]
            invalid = [l for l in de_bulk_text.splitlines() if l.strip() and ";" not in l]
            if de_bulk_lines:
                st.markdown(
                    f'<span class="badge badge-info">{len(de_bulk_lines)} poprawnych wpisów</span>',
                    unsafe_allow_html=True,
                )
            if invalid:
                st.warning(f"⚠️ {len(invalid)} linii bez średnika — zostaną pominięte")

    # ── Settings row ───────────────────────────────────────────────────────
    col_de1, col_de2, col_de3 = st.columns([1, 1, 2])
    with col_de1:
        de_scan_btn = st.button("▶ WERYFIKUJ", key="de_scan", use_container_width=True)
    with col_de2:
        de_delay = st.number_input("Opóźn. między req. (s)", 0.0, 10.0, 2.0, 0.5, key="de_delay")

    # ── Validation ─────────────────────────────────────────────────────────
    if not use_dataforseo:
        st.warning("⚠️ Włącz DataForSEO Search by Image w panelu bocznym.")
    if not anthropic_key:
        st.warning("⚠️ Podaj klucz Anthropic API w panelu bocznym.")

    # ── Run ────────────────────────────────────────────────────────────────
    if de_scan_btn:
        # Collect entries to process
        entries = []
        if de_input_mode == "📋 Pojedynczy wpis":
            if de_single_input and ";" in de_single_input:
                parts = de_single_input.split(";", 1)
                entries = [{"url": parts[0].strip(), "our_name": parts[1].strip()}]
        else:
            for line in de_bulk_lines:
                parts = line.split(";", 1)
                entries.append({"url": parts[0].strip(), "our_name": parts[1].strip()})

        if not entries:
            st.warning("Brak poprawnych wpisów do przetworzenia.")
        elif not dfs_login or not dfs_password:
            st.error("❌ Podaj login i hasło DataForSEO w panelu bocznym.")
        elif not anthropic_key:
            st.error("❌ Podaj klucz Anthropic API w panelu bocznym.")
        else:
            de_results = []
            prog = st.progress(0)
            status_de = st.empty()

            # Summary metrics (bulk)
            if len(entries) > 1:
                mc1, mc2, mc3, mc4 = st.columns(4)
                m_total  = mc1.empty()
                m_ok     = mc2.empty()
                m_corr   = mc3.empty()
                m_wrong  = mc4.empty()
                ok_cnt = corr_cnt = wrong_cnt = 0

            for idx, entry in enumerate(entries):
                img_url  = entry["url"]
                our_name = entry["our_name"]
                status_de.markdown(
                    f'<span class="tag">🇩🇪 [{idx+1}/{len(entries)}] {our_name[:50]}…</span>',
                    unsafe_allow_html=True,
                )

                res = {
                    "url": img_url, "our_name": our_name,
                    "dfs_raw": None, "organic": [],
                    "verification": None, "error": None,
                    "task_id": None,
                }

                # ── DataForSEO DE ─────────────────────────────────────────
                cache_key = f"de_{img_url}"
                cache_entry = st.session_state.dfs_tasks.get(cache_key, {})
                existing_tid = cache_entry.get("task_id")

                try:
                    if cache_entry.get("result"):
                        dfs_raw = cache_entry["result"]
                        res["dfs_from_cache"] = True
                    else:
                        dfs_raw, task_id = dfs_search_de(
                            img_url, dfs_login, dfs_password,
                            poll_interval, max_retries,
                            existing_task_id=existing_tid,
                        )
                        st.session_state.dfs_tasks[cache_key] = {
                            "task_id": task_id, "result": dfs_raw
                        }

                    res["dfs_raw"] = dfs_raw
                    parsed = parse_dfs_results(dfs_raw)
                    organic = parsed.get("organic", [])
                    res["dfs_keyword"] = parsed.get("keyword", "")

                    # ── Prioritise .de domains ───────────────────────────────────
                    de_first  = [o for o in organic if ".de/" in o.get("url","") or o.get("domain","").endswith(".de")]
                    de_others = [o for o in organic if o not in de_first]
                    organic   = de_first + de_others

                    # ── Crawl title + H1 ────────────────────────────────
                    if cache_entry.get("organic_crawled"):
                        organic = cache_entry["organic_crawled"]
                    else:
                        organic = crawl_de_organic(organic, max_items=8)
                        if cache_key in st.session_state.dfs_tasks:
                            st.session_state.dfs_tasks[cache_key]["organic_crawled"] = organic

                    res["organic"] = organic

                    # ── Claude Haiku verification ────────────────────────
                    if cache_entry.get("verification"):
                        res["verification"] = cache_entry["verification"]
                    else:
                        res["verification"] = claude_verify_german_name(
                            our_name, organic, anthropic_key,
                            model=selected_model,
                            dfs_keyword=res.get("dfs_keyword", ""),
                        )
                        if cache_key in st.session_state.dfs_tasks:
                            st.session_state.dfs_tasks[cache_key]["verification"] = res["verification"]

                except Exception as e:
                    res["error"] = str(e)
                    # Save task_id on timeout
                    err_msg = str(e)
                    m_tid = re.search(r"task_id: ([\w-]+)", err_msg)
                    if m_tid and cache_key not in st.session_state.dfs_tasks:
                        st.session_state.dfs_tasks[cache_key] = {
                            "task_id": m_tid.group(1), "result": None
                        }

                de_results.append(res)
                prog.progress((idx + 1) / len(entries))

                # Update metrics
                if len(entries) > 1:
                    ok_cnt += 1 if not res.get("error") else 0
                    v = res.get("verification") or {}
                    if v.get("our_name_correct") is True:
                        corr_cnt += 1
                    elif v.get("our_name_correct") is False:
                        wrong_cnt += 1

                    m_total.markdown(f'<div class="metric-box"><div class="metric-value">{idx+1}</div><div class="metric-label">Przetworzone</div></div>', unsafe_allow_html=True)
                    m_ok.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#22c55e">{ok_cnt}</div><div class="metric-label">Sukces</div></div>', unsafe_allow_html=True)
                    m_corr.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#22c55e">{corr_cnt}</div><div class="metric-label">Nazwa OK</div></div>', unsafe_allow_html=True)
                    m_wrong.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#f97316">{wrong_cnt}</div><div class="metric-label">Nazwa do poprawy</div></div>', unsafe_allow_html=True)

                if de_delay > 0 and idx < len(entries) - 1:
                    time.sleep(de_delay)

            status_de.markdown(
                '<span class="tag" style="color:#22c55e;">✅ Weryfikacja zakończona!</span>',
                unsafe_allow_html=True,
            )

            # ── Render results ─────────────────────────────────────────────
            st.markdown("---")

            # ── Export CSV helper ──────────────────────────────────────────
            def _build_export_csv(results):
                import io, csv as _csv
                buf = io.StringIO()
                w = _csv.writer(buf, delimiter=";", quoting=_csv.QUOTE_MINIMAL)
                max_org = max((len(r.get("organic") or []) for r in results), default=0)
                name_cols = [f"pobrana_nazwa_{i+1}" for i in range(max_org)]
                url_cols  = [f"url_nazwa_{i+1}"     for i in range(max_org)]
                w.writerow(["nasza_nazwa","proponowana_nazwa"] + name_cols + url_cols
                            + ["marka","sku_model","ean","pewnosc","nazwa_ok","blad"])
                for r in results:
                    v = r.get("verification") or {}
                    proposed = v.get("de_name_proposed") or v.get("de_product_name") or ""
                    orgs = r.get("organic") or []
                    names = [org.get("crawled_title") or org.get("crawled_h1") or org.get("title","") for org in orgs]
                    urls  = [org.get("url","") for org in orgs]
                    names += [""] * (max_org - len(names))
                    urls  += [""] * (max_org - len(urls))
                    w.writerow([r["our_name"], proposed] + names + urls
                               + [v.get("brand",""), v.get("model_sku",""), v.get("ean",""),
                                  v.get("confidence",""), str(v.get("our_name_correct","")),
                                  r.get("error","")])
                return buf.getvalue()

            col_ex1, col_ex2 = st.columns([1, 3])
            with col_ex1:
                st.download_button(
                    "⬇️ Export CSV (średnik)",
                    data=_build_export_csv(de_results).encode("utf-8-sig"),
                    file_name="de_verifikacja.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_ex2:
                preview_rows = []
                for r in de_results:
                    v = r.get("verification") or {}
                    ok = v.get("our_name_correct")
                    preview_rows.append({
                        "Nasza nazwa": r["our_name"],
                        "Proponowana DE": v.get("de_name_proposed") or v.get("de_product_name") or "—",
                        "OK?": "✅" if ok is True else ("❌" if ok is False else "❓"),
                        "SKU": v.get("model_sku",""),
                        "EAN": v.get("ean",""),
                    })
                if preview_rows:
                    st.dataframe(pd.DataFrame(preview_rows).fillna(""), use_container_width=True, height=200)

            # ── Detail cards ───────────────────────────────────────────────
            for idx, r in enumerate(de_results):
                v        = r.get("verification") or {}
                is_ok    = v.get("our_name_correct")
                organic  = r.get("organic") or []
                proposed = v.get("de_name_proposed") or v.get("de_product_name") or "—"
                icon     = "✅" if is_ok is True else ("🔶" if is_ok is False else "❓")

                with st.expander(
                    f"{icon} #{idx+1} — {r['our_name']}  →  {proposed}",
                    expanded=(len(de_results) == 1),
                ):
                    col_img, col_ver = st.columns([1, 3])
                    with col_img:
                        try:
                            st.image(r["url"], width=160)
                        except Exception:
                            st.markdown("🖼️")

                    with col_ver:
                        if is_ok is True:
                            _n = r["our_name"]
                            st.success(f"✅ Nazwa **{_n}** jest poprawna na rynku DE")
                        elif is_ok is False:
                            _n = r["our_name"]
                            st.error(f"❌ Nazwa **{_n}** wymaga korekty dla rynku DE")
                        else:
                            st.warning("❓ Nie udało się ocenić nazwy")

                        if v.get("our_name_assessment"):
                            st.markdown(
                                f'<div style="font-size:12px;color:#94a3b8;margin:4px 0 10px;">'
                                f'💬 {v["our_name_assessment"]}</div>',
                                unsafe_allow_html=True,
                            )

                        cola, colb = st.columns(2)
                        with cola:
                            st.markdown('<span class="tag">Nasza nazwa</span>', unsafe_allow_html=True)
                            bc = "#22c55e" if is_ok else "#ef4444"
                            st.markdown(
                                f'<div style="font-size:18px;font-weight:700;color:#f8fafc;'
                                f'border-left:3px solid {bc};padding-left:10px;">{r["our_name"]}</div>',
                                unsafe_allow_html=True,
                            )
                        with colb:
                            st.markdown('<span class="tag">Proponowana nazwa DE</span>', unsafe_allow_html=True)
                            st.markdown(
                                f'<div style="font-size:18px;font-weight:700;color:#f97316;'
                                f'border-left:3px solid #f97316;padding-left:10px;">{proposed}</div>',
                                unsafe_allow_html=True,
                            )

                        mcols = st.columns(4)
                        for ci, (lbl, val) in enumerate([
                            ("Marka", v.get("brand")),
                            ("SKU/Model", v.get("model_sku")),
                            ("EAN", v.get("ean")),
                            ("Pewność", v.get("confidence")),
                        ]):
                            if val:
                                with mcols[ci]:
                                    st.markdown(f'<span class="tag">{lbl}</span>', unsafe_allow_html=True)
                                    st.markdown(f"`{val}`")

                        if v.get("notes"):
                            st.markdown(
                                f'<div style="font-size:11px;color:#475569;margin-top:6px;">📝 {v["notes"]}</div>',
                                unsafe_allow_html=True,
                            )

                    # ── Crawled organic examples ──────────────────────────
                    if organic:
                        st.markdown("---")
                        st.markdown('<span class="tag">◈ Pobrane nazwy ze stron — title + H1</span>',
                                    unsafe_allow_html=True)
                        for i, org in enumerate(organic):
                            domain_o = org.get("domain","")
                            t_dfs    = org.get("title","")
                            t_crawl  = org.get("crawled_title","")
                            h1       = org.get("crawled_h1","")
                            url_o    = org.get("url","#")
                            price_o  = org.get("price","")
                            cerr     = org.get("crawl_error","")

                            jina_ok  = bool((t_crawl or h1) and not cerr)
                            best     = t_crawl or h1 or t_dfs or "—"

                            if jina_ok:
                                method_html = '<span style="font-size:8px;background:#0f2a1a;color:#22c55e;padding:1px 5px;border-radius:2px;margin-left:6px;">Jina ✓</span>'
                            elif cerr:
                                method_html = f'<span style="font-size:8px;background:#2a1212;color:#ef4444;padding:1px 5px;border-radius:2px;margin-left:6px;">403/błąd</span>'
                            else:
                                method_html = ""

                            h1_row   = f'<div style="display:grid;grid-template-columns:60px 1fr;gap:4px;margin-top:2px;"><span style="font-size:9px;color:#334155;text-transform:uppercase;">H1:</span><span style="font-size:12px;color:#f97316;">{h1[:120]}</span></div>' if (h1 and h1 != best) else ""
                            dfs_row  = f'<div style="display:grid;grid-template-columns:60px 1fr;gap:4px;margin-top:2px;"><span style="font-size:9px;color:#334155;text-transform:uppercase;">DFS:</span><span style="font-size:11px;color:#475569;">{t_dfs[:100]}</span></div>' if (t_dfs and t_dfs != best) else ""
                            price_row = f'<div style="font-size:11px;color:#f97316;margin-top:3px;font-weight:600;">💰 {price_o}</div>' if price_o else ""

                            st.markdown(f"""<div class="source-item" style="margin-bottom:8px;">
  <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">
    <span style="font-size:9px;color:#475569;letter-spacing:2px;">#{i+1} {domain_o}</span>
    {method_html}
    {f'<span style="font-size:9px;color:#ef4444;">{cerr}</span>' if cerr else ""}
  </div>
  <div style="display:grid;grid-template-columns:60px 1fr;gap:4px;align-items:baseline;">
    <span style="font-size:9px;color:#334155;text-transform:uppercase;">Nazwa:</span>
    <a href="{url_o}" target="_blank" style="font-size:14px;font-weight:700;color:#e2e8f0;text-decoration:none;">{best[:120]}</a>
  </div>
  {h1_row}{dfs_row}{price_row}
</div>""", unsafe_allow_html=True)

                    if r.get("error"):
                        st.warning(f"⚠️ {r['error']}")

            with st.expander(f"🐛 Debug JSON #{idx+1} — DataForSEO DE", expanded=False):
                if r.get("dfs_raw"):
                    st.json(r["dfs_raw"])
                else:
                    st.info("Brak danych")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center; font-size:9px; letter-spacing:3px; color:#1e293b; text-transform:uppercase; padding: 20px 0;">
    Product Scanner • Claude Vision + DataForSEO Search by Image API
</div>
""", unsafe_allow_html=True)

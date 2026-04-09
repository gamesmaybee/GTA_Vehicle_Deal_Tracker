"""
GTA Online Weekly Deals Scraper
- Fetches the weekly sticky post from r/gtaonline
- Parses discount vehicles, Luxury Autos, and Premium Deluxe Motorsport listings
- Fetches vehicle stats and images from GTA Fandom wiki
"""

import re
import time
import requests
from bs4 import BeautifulSoup

_REMOVED_TAG_RE = re.compile(r"\s*\(Removed Vehicle\)\s*", re.IGNORECASE)
_ANNOTATION_RE = re.compile(
    r"\s*\(available at [^)]+\)\s*"
    r"|\s*\(story mode only\)\s*"
    r"|\s*\(GTA\+[^)]*\)\s*",
    re.IGNORECASE
)

def strip_removed_tag(raw: str) -> tuple[str, bool]:
    """Return (clean_name, is_removed). Detects inline removal/annotation tags."""
    raw = _ANNOTATION_RE.sub("", raw).strip()
    if _REMOVED_TAG_RE.search(raw):
        return _REMOVED_TAG_RE.sub("", raw).strip(), True
    return raw.strip(), False



HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
INTEL_BASE = "https://rockstarintel.com"
GTA_WIKI_BASE = "https://gta.wiki/w"

# Patterns that match RockstarINTEL weekly event article slugs
WEEKLY_SLUG_PATTERNS = [
    r"gta.online.event.week",
    r"new.gta.online.event",
    r"gta.online.weekly.update",
    r"weekly.bonuses",
]


def fetch_weekly_post():
    """Fetch the latest GTA Online weekly update article from RockstarINTEL.
    Finds the most recent weekly event article on the homepage and parses it.
    """
    import time as _time

    for attempt in range(3):
        try:
            _time.sleep(1 + attempt * 2)
            r = requests.get(INTEL_BASE, headers=HEADERS, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Find the first (most recent) weekly article link
            seen = set()
            article_url = None
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href.startswith(INTEL_BASE + "/"):
                    continue
                if href in seen:
                    continue
                seen.add(href)
                slug = href.replace(INTEL_BASE + "/", "").lower()
                if any(re.search(p, slug) for p in WEEKLY_SLUG_PATTERNS):
                    article_url = href
                    break

            if not article_url:
                print(f"No weekly article found on attempt {attempt+1}")
                continue

            # Fetch the article
            _time.sleep(1)
            ra = requests.get(article_url, headers=HEADERS, timeout=30)
            ra.raise_for_status()
            article_soup = BeautifulSoup(ra.text, "html.parser")

            # Extract title
            title_el = article_soup.find("h1")
            title = title_el.get_text(strip=True) if title_el else ""

            # Extract article body text
            article_el = article_soup.find("article") or article_soup.find(
                "div", class_=re.compile(r"entry|post|content|article", re.I)
            )
            body = article_el.get_text("\n") if article_el else article_soup.get_text("\n")

            print(f"Found article: {title}")
            return {
                "title": title,
                "body": body,
                "url": article_url,
                "source": "rockstarintel",
            }

        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            continue

    return None


def parse_date_range(title: str) -> str:
    """Extract 'April 2nd to April 9th' from the title."""
    m = re.search(r"[-–]\s*(.+?)(?:\s*\(|$)", title)
    if m:
        return m.group(1).strip()
    return title



# ─── Post Parser ─────────────────────────────────────────────────────────────

def _line_matches_header(line: str, header: str) -> bool:
    """Match a section header line even if wrapped in markdown # / ** / links."""
    # Strip leading #s, **, links, and non-breaking spaces then compare
    cleaned = re.sub(r"^#+\s*", "", line.strip())          # remove leading #
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)  # strip links
    cleaned = re.sub(r"\*+", "", cleaned)                   # strip bold markers
    cleaned = cleaned.replace("\xa0", " ").strip().lower()
    return cleaned.startswith(header.lower())


def _is_section_break(line: str) -> bool:
    """Return True if this line starts a new top-level section."""
    stripped = line.strip()
    if re.match(r"^#+\s+", stripped):
        return True
    # Bold-only lines used as sub-headers e.g. "**30% Off**"
    if re.match(r"^\*{2}[^*]+\*{2}\s*$", stripped):
        return True
    return False


def extract_section(body: str, header: str) -> list[dict]:
    """Return bullet items under a given markdown section header as dicts with name + removed flag."""
    lines = body.splitlines()
    in_section = False
    items = []
    for line in lines:
        stripped = line.strip()
        if not in_section:
            if _line_matches_header(stripped, header):
                in_section = True
            continue
        # Stop at the next section header (but not sub-headers like **30% Off**)
        if re.match(r"^#+\s+", stripped) and not _line_matches_header(stripped, header):
            break
        if stripped.startswith(("-", "*")):
            item = re.sub(r"^[-*]\s*", "", stripped)
            item = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", item)
            item = re.sub(r"\*+", "", item)
            item = item.replace("\xa0", " ").strip()
            if item:
                name, removed = strip_removed_tag(item)
                items.append({"name": name, "removed": removed})
    return items


def _parse_discount_block(lines, start_idx):
    """Parse bullet+percentage items from lines[start_idx] until next # section."""
    items = []
    current_pct = None
    discount_re = re.compile(r"(\d+)%\s*off", re.IGNORECASE)
    bullet_re = re.compile(r"^[-*]\s+(.+)")
    for line in lines[start_idx:]:
        stripped = line.strip()
        cleaned = re.sub(r"^#+\s*", "", stripped)
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"\*+", "", cleaned).replace("\xa0", " ").strip()
        if re.match(r"^#+\s+", stripped):
            break
        bullet_match = bullet_re.match(stripped)
        pct_match = discount_re.search(cleaned)
        if pct_match and not bullet_match:
            current_pct = int(pct_match.group(1))
            continue
        if bullet_match and current_pct:
            raw_name = bullet_match.group(1)
            raw_name = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", raw_name)
            raw_name = re.sub(r"\*+", "", raw_name).replace("\xa0", " ").strip()
            if raw_name:
                name, removed = strip_removed_tag(raw_name)
                items.append({"name": name, "discount": current_pct, "removed": removed})
    return items


def parse_all_discount_groups(body):
    """Parse all discount sections, returning named groups.
    Returns e.g.:
      [{"group": "Discounts", "vehicles": [...]},
       {"group": "Law Enforcement Vehicle Discounts", "vehicles": [...]}]
    """
    lines = body.splitlines()
    groups = []
    discount_header_re = re.compile(r"^#+\s+.*discounts?", re.IGNORECASE)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not discount_header_re.match(stripped):
            continue
        group_name = re.sub(r"^#+\s*", "", stripped)
        group_name = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", group_name)
        group_name = re.sub(r"\*+", "", group_name).replace("\xa0", " ")
        group_name = re.sub(r"\s*\(.*?\)\s*$", "", group_name).strip()
        vehicles = _parse_discount_block(lines, i + 1)
        if vehicles:
            groups.append({"group": group_name, "vehicles": vehicles})
    return groups


def parse_discounts(body):
    """Flat list of all discounted vehicles across all groups (backward compat)."""
    items = []
    for g in parse_all_discount_groups(body):
        items.extend(g["vehicles"])
    return items


def parse_law_enforcement_discounts(body):
    for g in parse_all_discount_groups(body):
        if "law enforcement" in g["group"].lower():
            return g["vehicles"]
    return []



def parse_showroom(body: str, header: str) -> list[dict]:
    """Parse Luxury Autos or Premium Deluxe Motorsport sections."""
    return extract_section(body, header)


# ─── Fandom Wiki ─────────────────────────────────────────────────────────────




def gtawiki_fetch_vehicle(vehicle_name: str) -> dict:
    """Fetch vehicle stats and image from gta.wiki.
    
    gta.wiki pages are named exactly after the vehicle with underscores,
    e.g. https://gta.wiki/w/Cheetah_Classic
    We try progressively shorter name variants until one returns 200.
    """
    # Known remaps: some vehicles have wiki pages under different names
    WIKI_NAME_OVERRIDES = {
        # Vehicles whose wiki page name differs significantly from their in-game name
        "rhino tank": "Rhino Tank",
        "vapid taxi": "Taxi_(HD_Universe)",
        "benefactor schafter": "Schafter_(second_generation)",
    }
    override = WIKI_NAME_OVERRIDES.get(vehicle_name.lower())
    if override:
        # Use the override directly as the only candidate
        candidates = [override]
    else:
        words = vehicle_name.split()
        candidates = []
        if len(words) >= 3:
            candidates.append(" ".join(words[1:]))   # drop manufacturer: "Cheetah Classic"
            candidates.append(" ".join(words[-2:]))  # last 2 words
            candidates.append(words[-1])             # last word only
        elif len(words) == 2:
            candidates.append(words[-1])             # "Ellie"
            # Never try the manufacturer name alone — leads to manufacturer pages
        candidates.append(vehicle_name)              # full name last
        # Remove single-word candidates that are known manufacturer names
        MANUFACTURERS = {
            "bravado", "vapid", "declasse", "grotti", "albany", "western",
            "lampadati", "ocelot", "annis", "benefactor", "canis", "coil",
            "dinka", "enus", "hijak", "imponte", "invetero", "jacksheepe",
            "jobuilt", "karin", "maibatsu", "mammoth", "nagasaki", "obey",
            "pegassi", "pfister", "principe", "schyster", "truffade",
            "übermacht", "ubermacht", "vulcar", "weeny", "willard", "zirconium",
        }
        candidates = [c for c in candidates
                      if c.lower() not in MANUFACTURERS]

    headers = {"User-Agent": "GTADealsBot/1.0"}
    soup = None
    final_url = None

    def has_vehicle_content(page_soup) -> bool:
        """Return True if this page looks like a real vehicle article.
        Requires at least one non-UI image and some meaningful text content.
        """
        imgs = [i.get("src", "") for i in page_soup.find_all("img")
                if "Wiki.png" not in i.get("src", "")
                and "weirdgloop" not in i.get("src", "")
                and "footer" not in i.get("src", "")]
        text = page_soup.get_text(" ", strip=True)
        # Reject near-empty pages (disambiguation/stubs have very little text)
        if len(text) < 300:
            return False
        # Must have at least one image beyond UI chrome
        return len(imgs) > 0

    # Expand candidates to also include _(HD_Universe) variants
    expanded = []
    for c in candidates:
        expanded.append(c)
        expanded.append(f"{c} (HD Universe)")
    candidates = expanded

    raw_html = ""
    for candidate in candidates:
        url = f"{GTA_WIKI_BASE}/{candidate.replace(' ', '_')}"
        try:
            r = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
            if r.status_code != 200 or "Special:Search" in r.url:
                continue
            page_soup = BeautifulSoup(r.text, "html.parser")
            if has_vehicle_content(page_soup):
                soup = page_soup
                final_url = r.url
                raw_html = r.text
                break
        except Exception:
            continue

    if not soup:
        return {}

    try:
        # ── Image ──────────────────────────────────────────────────────────
        image_url = None

        def make_absolute(src: str) -> str:
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                return "https://gta.wiki" + src
            return src

        all_imgs = soup.find_all("img")
        img_srcs = [make_absolute(img.get("src", "")) for img in all_imgs
                    if img.get("src", "") and not img.get("src", "").endswith(".svg")
                    and "weirdgloop" not in img.get("src", "")
                    and "Wiki.png" not in img.get("src", "")
                    and "Logo-" not in img.get("src", "")]

        # Words in filenames that indicate non-vehicle-photo images to skip
        BAD_IMG_KEYWORDS = (
            "Badge", "badge", "Logo", "logo", "Icon", "icon",
            "RGSC", "Action", "Cutscene", "Interior", "Dashboard",
            "ColorBlock", "color", "Exhaust", "Engine", "Bumper",
            "Splitter", "Paint", "Wheel", "Horn", "Livery",
            "Artwork", "artwork", "Delivery", "Narc", "Mission",
            "Heist", "heist", "Trailer", "trailer", "Promo",
            "Blips", "blips", "Blip", "-GTAA", "-GTAIII", "-GTA3",
            "-GTAVC", "-GTASA", "-Sprite", "Sprite", "Pixel",
            "Warstock", "warstock", "Store", "Shop", "Website",
        )

        def is_good_img(s):
            return not any(kw in s for kw in BAD_IMG_KEYWORDS)

        def upscale(s):
            return re.sub(r"\d+px-", "600px-", s)

        def img_size(s):
            """Extract the pixel width from a thumbnail URL, e.g. 300px- -> 300."""
            m = re.search(r"/(\d+)px-", s)
            return int(m.group(1)) if m else 0

        FRONT_KEYWORDS = ("-front", "-Front", "FrontQuarter", "frontquarter")

        # Priority 1: front-facing GTA Online image (largest first)
        candidates_p1 = sorted(
            [s for s in img_srcs if any(k in s for k in FRONT_KEYWORDS)
             and "-GTAO" in s and is_good_img(s)],
            key=img_size, reverse=True
        )
        if candidates_p1:
            image_url = upscale(candidates_p1[0])

        # Priority 2: any good GTA Online image (largest first)
        if not image_url:
            candidates_p2 = sorted(
                [s for s in img_srcs if "-GTAO" in s and is_good_img(s)],
                key=img_size, reverse=True
            )
            if candidates_p2:
                image_url = upscale(candidates_p2[0])

        # Priority 3: any good GTA V image (largest first)
        if not image_url:
            candidates_p3 = sorted(
                [s for s in img_srcs if "-GTAV" in s and is_good_img(s)],
                key=img_size, reverse=True
            )
            if candidates_p3:
                image_url = upscale(candidates_p3[0])

        # Priority 4: largest image that passes filters
        if not image_url:
            candidates_p4 = sorted(
                [s for s in img_srcs if is_good_img(s)],
                key=img_size, reverse=True
            )
            if candidates_p4:
                image_url = upscale(candidates_p4[0])

        # ── Stats from vehicle statistics table ────────────────────────
        stats = {}
        # Collect all stats tables, prefer GTA V/Online ones
        all_stats_tables = []
        for table in soup.find_all("table", class_="wikitable"):
            ths = [th.get_text(" ", strip=True) for th in table.find_all("th")]
            header_text = " ".join(ths).lower()
            is_stats_table = (
                "max velocity" in header_text or
                "maximum velocity" in header_text or
                ("top speed" in header_text and "drivetrain" in header_text)
            )
            if not is_stats_table:
                continue
            # Check title row only for game label (not all cells)
            title_rows = [r for r in (table.find("tbody") or table).find_all("tr", recursive=False)[:2]
                         if r.find("th") and not r.find("td")]
            title_text = " ".join(r.get_text(" ", strip=True) for r in title_rows).lower()
            is_gta5 = ("grand theft auto v" in title_text or "gta online" in title_text
                       or "gta v" in title_text or "grand theft auto online" in title_text)
            all_stats_tables.append((is_gta5, table))
        # Sort so GTA V/Online tables come first
        all_stats_tables.sort(key=lambda x: x[0], reverse=True)
        for _, table in all_stats_tables:
            tbody = table.find("tbody") or table
            rows = tbody.find_all("tr", recursive=False)
            if len(rows) < 2:
                continue

            # Find the column header row (has multiple th with stat names)
            col_row = None
            for row in rows:
                cells = row.find_all("th")
                if len(cells) >= 3 and any(
                    k in " ".join(c.get_text(" ", strip=True).lower() for c in cells)
                    for k in ("speed", "velocity", "gears", "drivetrain")
                ):
                    col_row = row
                    break
            if not col_row:
                continue

            # Build clean column names, skipping empty header cells
            col_names = []
            for th in col_row.find_all("th"):
                text = th.get_text(" ", strip=True)
                text = re.sub(r"\s*\(.*?\)", "", text).strip()
                text = re.sub(r"\s+", " ", text)
                if text:  # skip empty th (row-label column)
                    col_names.append(text)

            # Find the best data row — prefer GTA Online, fall back to any td row
            data_row = None
            for row in rows:
                row_th = row.find("th")
                tds = row.find_all("td")
                if len(tds) >= 2:
                    # Prefer GTA Online row
                    if row_th and "online" in row_th.get_text(strip=True).lower():
                        data_row = tds
                        break
                    if data_row is None:
                        data_row = tds

            if data_row:
                for i, td in enumerate(data_row):
                    if i < len(col_names):
                        key = col_names[i]
                        val = td.get_text(" ", strip=True)
                        val = re.sub(r"\s+", " ", val).strip()
                        if key and val and val not in ("N/A", "—", "-", ""):
                            stats[key] = val
            break

        # ── Price & Store ────────────────────────────────────────────────────
        price = stats.get('Price', stats.get('price', ''))
        store = ''
        previously_available = False
        if not price:
            import re as _re
            from html import unescape as _ue
            decoded = _ue(raw_html)
            # Extract group1_data1 (price) field - never group1_data2 (trade price)
            # Use a broader match that handles  control chars in wiki markup
            pf = _re.search(r'group1_data1[^:]*:[^"]*"([\s\S]{0,3000})(?:"|(?=group1_label))', decoded)
            if pf:
                # Strip wiki parser strip markers (...) that break regex
                field = re.sub(r"[^]*", "", pf.group(1))
                # Check if vehicle is no longer available (removed)
                if 'no longer available' in field.lower():
                    previously_available = True
                # Match price + store. Wiki uses ''italics'' for game names
                # Patterns handle both *$X and [[Money|$]]X formats
                # Game label may be ''GTA Online'' or GTA Online
                pp_online = r"(?:\*\s*|\[\[Money[^\]]*\]\]|^)\$?([\d,]+)[^\n*]*?(?:''GTA Online''|GTA Online|Grand Theft Auto Online)"
                pp_gtav   = r"(?:\*\s*|\[\[Money[^\]]*\]\]|^)\$?([\d,]+)[^\n*]*?(?:''GTA V''|GTA V|Grand Theft Auto V)"
                pp_store  = r"(?:\*\s*|\[\[Money[^\]]*\]\])\$?([\d,]+)[^\n*]*?\(([^)]*(?:Motorsport|Autos|Carry|Customs|Works|Club|[Gg]arage|Hangar|Travel|Arena|[Ss]hop|[Ss]tore)[^)]*)\)"
                pp_any    = r"(?:\*\s*|\[\[Money[^\]]*\]\])\$?([\d,]+)"
                # Try online first, then gtav, then store-name match, then any
                om = _re.search(pp_online, field, _re.IGNORECASE)
                gm = _re.search(pp_gtav,   field, _re.IGNORECASE)
                sm = _re.search(pp_store,  field, _re.IGNORECASE)
                am = _re.search(pp_any,    field, _re.IGNORECASE)
                hit = om or gm or sm or am
                if hit:
                    price = '$' + hit.group(1)
                    # Extract store from same match or from any parenthetical
                    store_raw = ''
                    if hasattr(hit, 'lastindex') and hit.lastindex and hit.lastindex >= 2:
                        try: store_raw = hit.group(2)
                        except: pass
                    # Don't try to extract store from wiki links here —
                    # the dedicated store extraction block below handles this better
                    if store_raw:
                        store_raw = _re.sub(r'\[\[([^|]+\|)?([^\]]+)\]\]', r'\2', store_raw)
                        store_raw = _re.sub(r"'{2,}", '', store_raw).strip()
                        store = store_raw
            # If price found but no store yet, extract from price field
            if price and not store:
                price_num = price.replace('$', '').replace(',', '')
                parts = _re.split(r'[\\]n|\n', field)
                for ln in parts:
                    if price_num not in ln.replace(',', ''):
                        continue
                    # Strip HTML and wiki markup
                    clean = _re.sub(r'<[^>]+>', ' ', ln)
                    # Replace [[A|B]] with B, [[A]] with A
                    clean = _re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', clean)
                    clean = _re.sub(r"''+", '', clean)
                    clean = _re.sub(r'\s+', ' ', clean).strip()
                    # Try two store patterns:
                    # 1) Store before game label: (Store Name) (GTA Online)
                    # 2) Store after game label: GTA Online, Store Name)
                    GAME = _re.compile(r'GTA|Grand Theft|Online|Edition|Enhanced|E&E', _re.I)
                    for pat in [
                        r'\(([A-Za-z][^)]{4,50})\)\s*\(',
                        r',\s*([A-Za-z][^,)]{4,50})\s*\)',
                    ]:
                        m = _re.search(pat, clean)
                        if m:
                            cand = m.group(1).strip()
                            if not GAME.search(cand):
                                store = cand
                                break
                    if store:
                        break
            # Still no store — try [[Store]] wiki links, skipping categories and game names
            if price and not store:
                store_links = _re.findall(r'\[\[([^|\]:]+)(?:\|[^\]]+)?\]\]', field)
                SKIP_STORE = {
                    'money', 'gta online', 'gta v', 'grand theft auto online',
                    'grand theft auto v', 'grand theft auto v and online',
                    'expanded and enhanced',
                }
                for sl in store_links:
                    sl_clean = sl.strip()
                    if (sl_clean.lower() not in SKIP_STORE
                            and not sl_clean.startswith(":")
                            and not _re.search(r"Edition|Enhanced|Series|category", sl_clean, _re.IGNORECASE)
                            and len(sl_clean) > 3):
                        store = sl_clean
                        break
            if not price:
                text = soup.get_text('\n')
                for pat in [r"''GTA Online''|GTA Online|Grand Theft Auto Online",
                            r"''GTA V''|GTA V|Grand Theft Auto V"]:
                    for ln in text.splitlines():
                        if _re.search(r'\$[\d,]+', ln) and _re.search(pat, ln, _re.IGNORECASE):
                            pm = _re.search(r'\$[\d,]+', ln)
                            if pm:
                                price = pm.group(0)
                                break
                    if price:
                        break
        return {
            "wiki_url": final_url or "",
            "image": image_url,
            "price": price,
            "store": store,
            "previously_available": previously_available,
            "stats": stats,
        }
    except Exception as e:
        return {"error": str(e)}


def fandom_fetch_vehicle(vehicle_name: str) -> dict:
    """Fallback: fetch vehicle data from GTA Fandom wiki using their REST API.
    Fandom blocks browser scrapers but allows the REST API endpoint.
    """
    # Use Fandom's opensearch to find the page title
    search_url = "https://gta.fandom.com/api.php"
    params = {
        "action": "opensearch",
        "search": vehicle_name,
        "limit": 5,
        "namespace": 0,
        "format": "json",
    }
    try:
        r = requests.get(search_url, params=params, timeout=10,
                         headers={"User-Agent": "GTADealsBot/1.0"})
        results = r.json()
        titles = results[1] if len(results) > 1 else []
        urls = results[3] if len(results) > 3 else []

        # Pick best matching title
        best_title = None
        best_url = None
        name_lower = vehicle_name.lower()
        for title, url in zip(titles, urls):
            t = title.lower()
            if all(w in t for w in name_lower.split()[-2:]):
                best_title = title
                best_url = url
                break
        if not best_title and titles:
            best_title = titles[0]
            best_url = urls[0] if urls else None

        if not best_title:
            return {}

        # Fetch the page content via Fandom parse API (not blocked)
        parse_params = {
            "action": "parse",
            "page": best_title,
            "prop": "text",
            "format": "json",
        }
        rp = requests.get(search_url, params=parse_params, timeout=15,
                          headers={"User-Agent": "GTADealsBot/1.0"})
        page_data = rp.json()
        html = page_data.get("parse", {}).get("text", {}).get("*", "")
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")

        # Image from infobox - filter out event banners and non-vehicle images
        image_url = None
        FANDOM_BAD = (
            "Header", "header", "Banner", "banner", "Event", "event",
            "Logo", "logo", "Icon", "icon", "Badge", "badge",
            "Halloween", "Christmas", "Promo", "Artwork", "artwork",
            "Warstock", "warstock", "Store", "Website",
        )
        all_imgs = soup.find_all("img")
        for img in all_imgs:
            src = img.get("src", "")
            if not src or "data:image" in src or "wikia" not in src and "nocookie" not in src:
                continue
            if any(kw in src for kw in FANDOM_BAD):
                continue
            image_url = src
            break

        # Price
        price = ""
        price_m = re.search(r"\$[\d,]+", soup.get_text())
        if price_m:
            price = price_m.group(0)

        # Stats from infobox
        stats = {}
        if infobox:
            for row in infobox.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) == 2:
                    k = cells[0].get_text(strip=True)
                    v = cells[1].get_text(" ", strip=True)
                    if k and v and len(k) < 40:
                        stats[k] = v

        return {
            "wiki_url": best_url or "",
            "image": image_url,
            "price": price,
            "stats": stats,
        }
    except Exception as e:
        return {}


# Non-vehicle keywords — items with these words are not purchasable vehicles
NON_VEHICLE_KEYWORDS = {
    # Properties, businesses and upgrades — never vehicles
    "upgrades and modifications", "upgrade", "modification",
    "property", "office", "warehouse", "hangar", "facility",
    "bunker", "clubhouse", "bail office", "pass", "membership",
    # Specific non-vehicle discount items that appear in posts
    "body armor", "ammo",
}

def is_vehicle(name: str) -> bool:
    """Return False if the name looks like a property, upgrade, or non-vehicle item."""
    name_lower = name.lower()
    # Allow "Arena War" vehicles that have Arena in their name as a variant
    # but block pure property/upgrade entries
    import re as _re
    for kw in NON_VEHICLE_KEYWORDS:
        # Use word-boundary matching to avoid false positives like 'ammo' in 'Squaddie'
        if _re.search(r'\b' + _re.escape(kw) + r'\b', name_lower):
            return False
    return True


# ─── RockstarINTEL Parsers ───────────────────────────────────────────────────

def intel_parse_discounts(body: str) -> list[dict]:
    """Parse discounts from RockstarINTEL plain-text format."""
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    items = []
    in_discounts = False
    current_pct = None
    pct_re = re.compile(r"^(\d+)%\s*off\s*$", re.IGNORECASE)

    for line in lines:
        if line.lower() == "discounts":
            in_discounts = True
            continue
        if not in_discounts:
            continue
        # Stop at Bonuses or next major section
        if line.lower() in ("bonuses", "gun van contents", "weekly challenge"):
            break
        # Percentage header
        m = pct_re.match(line)
        if m:
            current_pct = int(m.group(1))
            continue
        # Vehicle line — skip if it looks like a non-vehicle
        if current_pct and line and not line.startswith(("2x", "3x", "4x", "GTA$")):
            name, removed = strip_removed_tag(line.replace("\xa0", " ").strip())
            if name and is_vehicle(name):
                items.append({"name": name, "discount": current_pct, "removed": removed})

    return items


def intel_parse_all_discount_groups(body: str) -> list[dict]:
    """Parse discounts grouped by percentage from RockstarINTEL format."""
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    groups = {}  # pct -> list of vehicles
    group_order = []
    in_discounts = False
    current_pct = None
    pct_re = re.compile(r"^(\d+)%\s*off\s*$", re.IGNORECASE)

    for line in lines:
        if line.lower() == "discounts":
            in_discounts = True
            continue
        if not in_discounts:
            continue
        if line.lower() in ("bonuses", "gun van contents", "weekly challenge"):
            break
        m = pct_re.match(line)
        if m:
            current_pct = int(m.group(1))
            if current_pct not in groups:
                groups[current_pct] = []
                group_order.append(current_pct)
            continue
        if current_pct and line and not line.startswith(("2x", "3x", "4x", "GTA$")):
            name, removed = strip_removed_tag(line.replace("\xa0", " ").strip())
            if name and is_vehicle(name):
                groups[current_pct].append({"name": name, "discount": current_pct, "removed": removed})

    # Convert to list of group dicts, merging LE vehicles into one group
    # Group LE vehicles (those with patrol/cruiser/pursuit/interceptor etc) separately
    LE_KEYWORDS = re.compile(r"cruiser|patrol|pursuit|interceptor|outreach|police bike|park ranger", re.I)
    result = []
    le_vehicles = []
    regular_vehicles = []

    for pct in group_order:
        for v in groups[pct]:
            if LE_KEYWORDS.search(v["name"]):
                le_vehicles.append(v)
            else:
                regular_vehicles.append(v)

    if le_vehicles:
        result.append({"group": "Law Enforcement Vehicle Discounts", "vehicles": le_vehicles})
    if regular_vehicles:
        result.append({"group": "Discounts", "vehicles": regular_vehicles})

    return result


def intel_parse_showroom(body: str, header_keyword: str) -> list[dict]:
    """Parse showroom vehicles from RockstarINTEL plain-text format.
    Vehicles are listed as a comma/ampersand separated list on the line
    after the section header.
    """
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if header_keyword.lower() in line.lower():
            # The vehicle list is usually 1-2 lines after the header
            for j in range(i+1, min(i+4, len(lines))):
                candidate = lines[j]
                # Skip descriptive sentences, look for comma/& separated names
                if "," in candidate or "&" in candidate:
                    # Split on comma and &
                    raw_names = re.split(r",|&", candidate)
                    vehicles = []
                    for raw in raw_names:
                        name = raw.replace(".", "").replace("\xa0", " ").strip()
                        if name and len(name) > 2:
                            name, removed = strip_removed_tag(name)
                            vehicles.append({"name": name, "removed": removed})
                    if vehicles:
                        return vehicles
    return []



def enrich_vehicle(name: str, discount: int | None = None, removed: bool = False) -> dict:
    time.sleep(0.3)  # polite rate limiting
    # Normalize unicode dashes to hyphens for wiki URL matching
    wiki_name = name.replace("–", "-").replace("—", "-")
    # Strip variant suffixes like (Arena), (Mk II), (Custom) for wiki lookup
    # but keep the original name for display
    wiki_name_clean = re.sub(r"\s*\((Arena|Custom|Mk\s*II|Mk\s*III|Weaponized|Armored)\)\s*$",
                             "", wiki_name, flags=re.IGNORECASE).strip()
    wiki_data = gtawiki_fetch_vehicle(wiki_name_clean)

    # Fall back to Fandom if gta.wiki is missing image or price
    if not wiki_data.get("image") or not wiki_data.get("price"):
        print(f"  Trying Fandom fallback for {name!r}...")
        fandom_data = fandom_fetch_vehicle(wiki_name)
        if not wiki_data.get("image") and fandom_data.get("image"):
            wiki_data["image"] = fandom_data["image"]
        if not wiki_data.get("price") and fandom_data.get("price"):
            wiki_data["price"] = fandom_data["price"]
        if not wiki_data.get("stats") and fandom_data.get("stats"):
            wiki_data["stats"] = fandom_data["stats"]
        if not wiki_data.get("wiki_url") and fandom_data.get("wiki_url"):
            wiki_data["wiki_url"] = fandom_data["wiki_url"]

    return {
        "name": name,
        "discount": discount,
        "removed": removed,
        "wiki_url": wiki_data.get("wiki_url", ""),
        "image": wiki_data.get("image", ""),
        "price": wiki_data.get("price", ""),
        "store": wiki_data.get("store", ""),
        "previously_available": wiki_data.get("previously_available", False),
        "stats": wiki_data.get("stats", {}),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def get_weekly_deals() -> dict:
    post = fetch_weekly_post()
    if not post:
        raise RuntimeError("Could not find weekly post on r/gtaonline")

    body = post["body"]
    date_range = parse_date_range(post["title"])

    # Use appropriate parsers based on source
    is_intel = post.get("source") == "rockstarintel"

    if is_intel:
        raw_luxury = intel_parse_showroom(body, "Luxury Autos")
        raw_pdm = intel_parse_showroom(body, "Premium Deluxe Motorsport")
        raw_groups = intel_parse_all_discount_groups(body)
    else:
        raw_luxury = parse_showroom(body, "Luxury Autos")
        raw_pdm = parse_showroom(body, "Premium Deluxe Motorsports")
        raw_groups = [g for g in parse_all_discount_groups(body)
                      if "gun van" not in g["group"].lower()]
    enriched_groups = []
    for group in raw_groups:
        vehicles = [v for v in group["vehicles"] if is_vehicle(v["name"])]
        print(f"Enriching {len(vehicles)} vehicles in group '{group['group']}'...")
        enriched = [enrich_vehicle(v["name"], v["discount"], v.get("removed", False))
                    for v in vehicles]
        enriched_groups.append({"group": group["group"], "vehicles": enriched})
    # Also keep flat list for backward compat
    discounts = [v for g in enriched_groups for v in g["vehicles"]]

    # Build a discount lookup so showroom vehicles can show their discount
    discount_lookup = {v["name"].lower(): v["discount"]
                       for g in enriched_groups for v in g["vehicles"]}

    print(f"Enriching {len(raw_luxury)} Luxury Autos vehicles...")
    luxury = [enrich_vehicle(v["name"],
                             discount=discount_lookup.get(v["name"].lower()),
                             removed=v.get("removed", False)) for v in raw_luxury]

    print(f"Enriching {len(raw_pdm)} PDM vehicles...")
    pdm = [enrich_vehicle(v["name"],
                          discount=discount_lookup.get(v["name"].lower()),
                          removed=v.get("removed", False)) for v in raw_pdm]

    return {
        "date_range": date_range,
        "post_url": post["url"],
        "post_title": post["title"],
        "discount_groups": enriched_groups,
        "discounts": discounts,
        "luxury_autos": luxury,
        "pdm": pdm,
    }


if __name__ == "__main__":
    import json, sys
    print("Fetching weekly deals...")
    data = get_weekly_deals()
    output_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_file}")
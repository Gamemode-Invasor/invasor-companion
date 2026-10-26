"""The Game tab's enrichers: a game's scores from public answers that need no key, and the pages to look further."""
import math
import urllib.parse

# GET only, no key. Steam's own appreviews redirects to its home page without a session: SteamSpy has the counts.
STEAMSPY = "https://steamspy.com/api.php?request=appdetails&appid={}"
APPDETAILS = "https://store.steampowered.com/api/appdetails?appids={}&filters=metacritic"
PROTONDB = "https://www.protondb.com/api/v1/reports/summaries/{}.json"
STORESEARCH = "https://store.steampowered.com/api/storesearch/?term={}&cc=us&l=english"

PROTONDB_PAGE = "https://www.protondb.com/"
HLTB_PAGE = "https://howlongtobeat.com/"
PAGES = (PROTONDB_PAGE, HLTB_PAGE)  # all that open_page may open
TIERS = ("platinum", "gold", "silver", "bronze", "borked", "pending")


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def steamdb_score(positive, negative):
    """The reviews' average corrected by their number (SteamDB's formula, as in Puntueitor), 0-100, or None."""
    total = positive + negative
    if total <= 0:
        return None
    average = positive / total
    return round((average - (average - 0.5) * 2 ** -math.log10(total + 1)) * 100, 1)


def rating(percent, total):
    """Steam's words for the reviews ("very_positive"…), from the share of positive ones and how many there are."""
    if percent >= 80:
        if total >= 500 and percent >= 95:
            return "overwhelmingly_positive"
        return "very_positive" if total >= 50 else "positive"
    if percent >= 70:
        return "mostly_positive"
    if percent >= 40:
        return "mixed"
    if percent >= 20:
        return "mostly_negative"
    if total >= 500:
        return "overwhelmingly_negative"
    return "very_negative" if total >= 50 else "negative"


def steam(steamspy):
    """{"rating", "percent", "total", "steamdb"} from SteamSpy's answer, or None without reviews."""
    if not isinstance(steamspy, dict):
        return None
    pos, neg = _count(steamspy.get("positive")), _count(steamspy.get("negative"))
    total = pos + neg
    if not total:
        return None
    percent = round(pos * 100 / total)
    return {"rating": rating(percent, total), "percent": percent, "total": total, "steamdb": steamdb_score(pos, neg)}


def metacritic(appdetails, appid):
    """{"score", "url"} from the store's appdetails, or None when the game has none."""
    data = appdetails.get(str(appid)) if isinstance(appdetails, dict) else None
    data = data.get("data") if isinstance(data, dict) and data.get("success") else None
    meta = data.get("metacritic") if isinstance(data, dict) else None
    score = meta.get("score") if isinstance(meta, dict) else None
    if not isinstance(score, int) or isinstance(score, bool) or not 0 < score <= 100:
        return None
    url = meta.get("url")
    return {"score": score, "url": url if isinstance(url, str) and url.startswith("https://") else None}


def protondb(summary):
    """{"tier", "total"} from ProtonDB's summary, or None."""
    tier = summary.get("tier") if isinstance(summary, dict) else None
    if tier not in TIERS:
        return None
    return {"tier": tier, "total": _count(summary.get("total"))}


def best_match(storesearch):
    """(appid, name) of the store search's first app, or None."""
    items = storesearch.get("items") if isinstance(storesearch, dict) else None
    for item in items if isinstance(items, list) else ():
        if isinstance(item, dict) and item.get("type") == "app" and isinstance(item.get("id"), int) and item["id"] > 0:
            return str(item["id"]), str(item.get("name") or "")
    return None


def storesearch_url(title):
    """Steam's store search for a non-Steam game's title."""
    return STORESEARCH.format(urllib.parse.quote(title, safe=""))


def protondb_url(appid, title, shortcut):
    """The game's ProtonDB page; a non-Steam game's is a search by its title."""
    if shortcut:
        return PROTONDB_PAGE + "search?q=" + urllib.parse.quote(title or "", safe="")
    return f"{PROTONDB_PAGE}app/{appid}"


def hltb_url(title):
    """HowLongToBeat's search for the title (it has no public API to read the hours from)."""
    return HLTB_PAGE + "?q=" + urllib.parse.quote(title or "", safe="")

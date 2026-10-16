from datetime import datetime, timezone
import pycountry, requests
from babel.numbers import get_territory_currencies
from django.conf import settings
from django.core.cache import cache


def get_rates():
    data = cache.get("fx:rates")
    if data:
        return data
    try:
        url = settings.FX_API_URL.format(key=settings.FX_API_KEY)
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        j = r.json()
        if j.get("result") != "success":
            raise ValueError("bad response")
        data = {
            "rates": j["rates"],
            "updated": datetime.fromtimestamp(j["time_last_update_unix"], timezone.utc).isoformat(),
            "live": True,
            "source": "ExchangeRate-API",
        }
        cache.set("fx:rates", data, 3600)
        cache.set("fx:stale", data, 7 * 86400)
        return data
    except Exception:
        stale = cache.get("fx:stale")
        return {**stale, "live": False} if stale else None


def get_countries(codes):
    out = cache.get("fx:countries")
    if out:
        return [c for c in out if c["currency"] in codes]
    out = []
    for c in pycountry.countries:
        try:
            cur = get_territory_currencies(c.alpha_2)
        except Exception:
            continue
        if cur:
            flag = "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in c.alpha_2)
            out.append({"code": c.alpha_2, "name": getattr(c, "common_name", c.name),
                        "flag": flag, "currency": cur[0]})
    out.sort(key=lambda x: x["name"])
    cache.set("fx:countries", out, 86400)
    return [c for c in out if c["currency"] in codes]
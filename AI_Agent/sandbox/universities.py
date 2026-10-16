import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_UNIVERSITIES_FILE = Path(__file__).resolve().parent / "data" / "universities.json"
_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_universities() -> List[Dict[str, Any]]:
    global _CACHE
    if _CACHE is None:
        with open(_UNIVERSITIES_FILE, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def reload_universities() -> List[Dict[str, Any]]:
    """Force reload of the universities reference data from disk."""
    global _CACHE
    _CACHE = None
    return _load_universities()


def list_universities() -> List[Dict[str, Any]]:
    """Return all reference universities."""
    return list(_load_universities())


def lookup_university(query: str) -> Optional[Dict[str, Any]]:
    """
    Look up a university by slug, exact name, or alias (case-insensitive).
    Checks the database first if available, then falls back to JSON reference data.
    """
    if not query or not query.strip():
        return None

    cleaned = query.strip().lower()

    # 1. Try querying Django University model if database is accessible
    try:
        from Agent.models import University as UniversityModel
        # Check exact slug
        uni = UniversityModel.objects.filter(slug__iexact=cleaned).first()
        if not uni:
            # Check name
            uni = UniversityModel.objects.filter(name__iexact=cleaned).first()
        if not uni:
            # Check icontains on name
            uni = UniversityModel.objects.filter(name__icontains=cleaned).first()
        if not uni:
            # Check aliases (JSON field)
            for item in UniversityModel.objects.all():
                aliases = [a.lower() for a in item.aliases or []]
                if cleaned in aliases or any(cleaned in a for a in aliases):
                    uni = item
                    break
        if uni:
            return {
                "slug": uni.slug,
                "name": uni.name,
                "country": uni.country,
                "aliases": uni.aliases,
                "payment_channels": uni.payment_channels,
                "common_issues": uni.common_issues,
                "support": uni.support,
                "source": "database",
            }
    except Exception:
        # Django DB may not be migrated or connection may be offline in some test setups
        pass

    # 2. Fall back to JSON reference data
    data = _load_universities()
    for item in data:
        if item.get("slug", "").lower() == cleaned:
            res = dict(item)
            res["source"] = "reference_data"
            return res
        if item.get("name", "").lower() == cleaned:
            res = dict(item)
            res["source"] = "reference_data"
            return res
        aliases = [a.lower() for a in item.get("aliases", [])]
        if cleaned in aliases or any(cleaned in a for a in aliases):
            res = dict(item)
            res["source"] = "reference_data"
            return res

    # 3. Partial substring match in name
    for item in data:
        if cleaned in item.get("name", "").lower():
            res = dict(item)
            res["source"] = "reference_data"
            return res

    return None


def seed_universities_to_db() -> int:
    """
    Seed reference universities into the Agent.models.University database table.
    Returns the count of created or updated records.
    """
    from Agent.models import University as UniversityModel

    data = _load_universities()
    count = 0
    for u in data:
        UniversityModel.objects.update_or_create(
            slug=u["slug"],
            defaults={
                "name": u["name"],
                "country": u["country"],
                "aliases": u.get("aliases", []),
                "payment_channels": u.get("payment_channels", []),
                "common_issues": u.get("common_issues", []),
                "support": u.get("support", {}),
            },
        )
        count += 1
    return count


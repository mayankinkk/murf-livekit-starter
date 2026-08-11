"""Day 5 domain-data tool for RupeeGPT: Indian government scheme eligibility.

RupeeGPT reads a public structured CSV dataset of Indian government schemes and
computes *preliminary* eligibility matches from a caller profile.

Dataset: "Indian Government Schemes 2025" by SmartDuke Technologies
(https://huggingface.co/datasets/smartduketech/indian-government-schemes-2025,
CC BY 4.0). Original source of the scheme information is India's official
myScheme portal (https://www.myscheme.gov.in/).

IMPORTANT:
- This is NOT a live government API. Nothing here queries the government.
- The dataset (Schemes.csv) is loaded once per process and cached.
- Matches are computed ONLY from the structured eligibility fields the dataset
  provides. We never invent criteria, never treat `eligibility_text` as a source
  of new rules, and never guess a caller value the agent did not supply.
- Every caller/scheme field that is missing is treated as "no restriction
  recorded" (for scheme criteria) or "not verified" (for caller facts). A
  missing caller fact simply disables that filter; it never fabricates an answer.
- Results are preliminary matches, never a guarantee of official eligibility.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent")

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "Schemes.csv"

DATASET_URL = (
    "https://huggingface.co/datasets/smartduketech/indian-government-schemes-2025"
)
SOURCE = "Public Indian Government Schemes dataset (SmartDuke Technologies, derived from myscheme.gov.in)"
DATA_NOTE = (
    "Public dataset derived from India's myScheme portal (myscheme.gov.in). "
    "This is NOT a live government API and may be incomplete or outdated."
)
DISCLAIMER = (
    "These are preliminary matches based on the available dataset. Verify current "
    "eligibility on the official scheme page before applying."
)

# Columns the matcher actually reads. If any of these are missing from the CSV
# header the dataset is considered unusable and the tool reports an error.
REQUIRED_COLUMNS = (
    "name",
    "state",
    "category",
    "benefits",
    "eligibility_text",
    "documents_required",
    "official_url",
    "apply_url",
    "ministry",
    "eligibility_age_min",
    "eligibility_age_max",
    "eligibility_gender",
    "eligibility_caste",
    "eligibility_income_max",
    "eligibility_residence",
    "eligibility_state",
    "eligibility_disability",
    "eligibility_bpl",
    "scraped_at",
)

# Financial Services is RupeeGPT's core domain, so schemes tagged with this
# category are ranked ahead of unrelated categories.
FINANCIAL_CATEGORY = "Banking,Financial Services and Insurance"
MAX_RESULTS = 8

# Canonical caste values as stored in the dataset (case-insensitive input maps
# onto these). "General" is kept in mixed case so reasons read naturally.
_CASTE_CANONICAL = {"SC": "SC", "ST": "ST", "OBC": "OBC", "GENERAL": "General"}


def _normalise_caste(value: str | None) -> str | None:
    if not value:
        return None
    return _CASTE_CANONICAL.get(value.strip().upper())


# Canonical dataset state names -> human-friendly aliases accepted from the
# caller (spoken states). Keys are normalized (lowercased, collapsed spaces).
_CANONICAL_STATES = (
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra & Nagar Haveli and Daman & Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)

_STATE_ALIASES: dict[str, str] = {
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "nct of delhi": "Delhi",
    "national capital territory of delhi": "Delhi",
    "pondicherry": "Puducherry",
    "orissa": "Odisha",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
    "a&n islands": "Andaman and Nicobar Islands",
    "daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
    "daman & diu": "Dadra & Nagar Haveli and Daman & Diu",
    "dadra and nagar haveli and daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
    "jammu kashmir": "Jammu and Kashmir",
    "jammu & kashmir": "Jammu and Kashmir",
    "uttaranchal": "Uttarakhand",
    "tamilnadu": "Tamil Nadu",
}
for _name in _CANONICAL_STATES:
    _STATE_ALIASES.setdefault(_name.lower(), _name)
# Short 2-letter codes map unambiguously to one canonical name.
for _code, _name in {
    "ap": "Andhra Pradesh",
    "ar": "Arunachal Pradesh",
    "as": "Assam",
    "br": "Bihar",
    "cg": "Chhattisgarh",
    "ch": "Chandigarh",
    "dl": "Delhi",
    "ga": "Goa",
    "gj": "Gujarat",
    "hr": "Haryana",
    "hp": "Himachal Pradesh",
    "jk": "Jammu and Kashmir",
    "jh": "Jharkhand",
    "ka": "Karnataka",
    "kl": "Kerala",
    "la": "Ladakh",
    "ld": "Lakshadweep",
    "mp": "Madhya Pradesh",
    "mh": "Maharashtra",
    "mn": "Manipur",
    "ml": "Meghalaya",
    "mz": "Mizoram",
    "nl": "Nagaland",
    "od": "Odisha",
    "pb": "Punjab",
    "py": "Puducherry",
    "rj": "Rajasthan",
    "sk": "Sikkim",
    "tn": "Tamil Nadu",
    "tg": "Telangana",
    "tr": "Tripura",
    "up": "Uttar Pradesh",
    "uk": "Uttarakhand",
    "wb": "West Bengal",
}.items():
    _STATE_ALIASES.setdefault(_code, _name)


class SchemeDataError(Exception):
    """Raised when the scheme dataset cannot be loaded or is unusable."""


# Module-level cache: (records, meta). Loaded once per process, guarded by a lock.
_CACHE: list[dict[str, Any]] | None = None
_CACHE_META: dict[str, Any] = {}
_CACHE_PATH: Path | None = None
_LOCK = threading.Lock()


def _normalise_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def canonical_state(value: str | None) -> str | None:
    """Map a caller-supplied state to the dataset's canonical state name.

    Returns None when the value cannot be mapped to a known state.
    """
    if not value:
        return None
    key = _normalise_key(value)
    if key in ("all", "any", "anywhere in india", "across india", "central"):
        return None  # "anywhere in India" is not a state to filter by
    return _STATE_ALIASES.get(key)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in ("null", "nan", "none", "n/a", "na"):
        return None
    text = text.replace(",", "")
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "y"):
        return True
    if text in ("false", "no", "0", "n"):
        return False
    return None


def _parse_list(value: Any) -> list[str]:
    """Parse a JSON-array string column (e.g. '["SC","ST"]')."""
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in ("null", "nan", "[]"):
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _parse_documents(raw: Any) -> list[str]:
    """Split a numbered/bulleted document list into a clean string list."""
    if not raw:
        return []
    docs: list[str] = []
    for line in str(raw).splitlines():
        cleaned = re.sub(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)+", "", line).strip()
        if not cleaned:
            continue
        if cleaned not in docs:
            docs.append(cleaned)
    return docs[:10]


def _trim(text: Any, limit: int = 500) -> str:
    if not text:
        return ""
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value[:limit]


def _parse_scheme(row: dict[str, Any]) -> dict[str, Any]:
    """Turn one CSV row into a typed record for matching."""
    caste = _parse_list(row.get("eligibility_caste"))
    caste = [value for value in (_normalise_caste(c) for c in caste) if value]

    eligibility_state = _parse_list(row.get("eligibility_state"))
    if not eligibility_state:
        logger.warning(
            "[SCHEMES] row %r has no eligibility_state; treating as all-India",
            row.get("name"),
        )
        eligibility_state = ["All"]

    gender = str(row.get("eligibility_gender") or "all").strip().lower()
    if gender not in ("male", "female"):
        gender = "all"
    residence = str(row.get("eligibility_residence") or "both").strip().lower()
    if residence not in ("rural", "urban"):
        residence = "both"

    return {
        "name": (row.get("name") or "").strip(),
        "description": _trim(row.get("description"), 300),
        "ministry": (row.get("ministry") or "").strip(),
        "state": (row.get("state") or "").strip() or "Central",
        "category": (row.get("category") or "").strip(),
        "benefits": _trim(row.get("benefits"), 600),
        "eligibility_text": _trim(row.get("eligibility_text"), 500),
        "documents_required": _parse_documents(row.get("documents_required")),
        "apply_url": (row.get("apply_url") or "").strip(),
        "official_url": (row.get("official_url") or "").strip(),
        "age_min": _parse_int(row.get("eligibility_age_min")),
        "age_max": _parse_int(row.get("eligibility_age_max")),
        "gender": gender,
        "caste": caste,
        "income_max": _parse_int(row.get("eligibility_income_max")),
        "residence": residence,
        "eligibility_state": eligibility_state,
        "disability": _parse_bool(row.get("eligibility_disability")),
        "bpl": _parse_bool(row.get("eligibility_bpl")),
        "scraped_at": (row.get("scraped_at") or "").strip(),
    }


def _load_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read and parse the CSV at ``path``. Raises SchemeDataError on failure."""
    if not path.is_file():
        raise SchemeDataError(f"scheme dataset not found at {path}")

    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError) as exc:
        raise SchemeDataError(f"could not read scheme dataset: {exc}") from exc

    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing:
        raise SchemeDataError(
            f"scheme dataset is missing required columns: {', '.join(missing)}"
        )

    records = [_parse_scheme(row) for row in rows if row.get("name")]

    data_as_of: str | None = None
    latest: datetime | None = None
    for record in records:
        scraped = record["scraped_at"]
        if not scraped:
            continue
        try:
            parsed = datetime.fromisoformat(scraped.replace("+00", "+00:00"))
        except (TypeError, ValueError):
            continue
        if latest is None or parsed > latest:
            latest = parsed
    if latest is not None:
        data_as_of = latest.date().isoformat()

    meta = {
        "record_count": len(records),
        "data_as_of": data_as_of,
    }
    logger.info(
        "[SCHEMES] loaded %d schemes from %s (data_as_of=%s)",
        len(records),
        path.name,
        data_as_of,
    )
    return records, meta


def load_schemes(
    path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the dataset once per process and return ``(records, meta)``.

    Pass an explicit ``path`` (used by tests) to read that file instead; a
    non-default path bypasses the cache. Raises :class:`SchemeDataError` when the
    dataset is missing or unusable.
    """
    global _CACHE, _CACHE_META, _CACHE_PATH
    target = Path(path) if path is not None else DATASET_PATH
    with _LOCK:
        if _CACHE is not None and target == _CACHE_PATH:
            return _CACHE, dict(_CACHE_META)
        records, meta = _load_file(target)
        if path is None:
            _CACHE = records
            _CACHE_META = meta
            _CACHE_PATH = target
        return records, dict(meta)


def clear_cache() -> None:
    """Drop the in-memory dataset cache (used by tests)."""
    global _CACHE, _CACHE_META, _CACHE_PATH
    with _LOCK:
        _CACHE = None
        _CACHE_META = {}
        _CACHE_PATH = None


def _is_financial(scheme: dict[str, Any]) -> bool:
    return FINANCIAL_CATEGORY in scheme["category"]


def _category_relevance(scheme: dict[str, Any], profile: dict[str, Any]) -> bool:
    category = scheme["category"]
    if profile.get("student") and "Education & Learning" in category:
        return True
    occupation = (profile.get("occupation") or "").lower()
    if any(word in occupation for word in ("farm", "agricultur", "kisan")):
        return "Agriculture" in category
    if any(
        word in occupation
        for word in (
            "business",
            "self-employed",
            "enterprise",
            "entrepreneur",
            "shop",
            "street vendor",
        )
    ) or profile.get("self_employed"):
        return (
            "Business & Entrepreneurship" in category
            or "Skills & Employment" in category
        )
    return False


def _evaluate(
    scheme: dict[str, Any], profile: dict[str, Any]
) -> tuple[bool, list[str], int]:
    """Return ``(eligible, reason_clauses, verified_criteria_count)``."""
    clauses: list[str] = []
    verified = 0

    caller_state = profile.get("state")
    scheme_states = scheme["eligibility_state"]
    if caller_state:
        if "All" in scheme_states:
            clauses.append("Central scheme available in all states")
            verified += 1
        elif caller_state in scheme_states:
            clauses.append(f"available in {caller_state}")
            verified += 1
        else:
            return False, [], 0
    else:
        # Caller's state is unknown: only all-India schemes can be returned, so
        # we never surface a scheme that is tied to another state.
        if "All" not in scheme_states:
            return False, [], 0
        clauses.append("state not verified; central scheme only")

    caller_age = profile.get("age")
    if caller_age is None:
        clauses.append("age not verified")
    else:
        if scheme["age_min"] is not None and caller_age < scheme["age_min"]:
            return False, [], 0
        if scheme["age_max"] is not None and caller_age > scheme["age_max"]:
            return False, [], 0
        if scheme["age_min"] is None and scheme["age_max"] is None:
            clauses.append("no age limit recorded")
        elif scheme["age_min"] == scheme["age_max"]:
            clauses.append(
                f"age {caller_age} matches the {scheme['age_min']}-year requirement"
            )
        else:
            bounds = "-".join(
                part
                for part in (
                    str(scheme["age_min"]) if scheme["age_min"] is not None else "",
                    str(scheme["age_max"]) if scheme["age_max"] is not None else "",
                )
                if part
            )
            clauses.append(f"age {caller_age} is within {bounds}")
        verified += 1

    caller_income = profile.get("annual_income")
    if caller_income is None:
        clauses.append("income not verified")
    else:
        if scheme["income_max"] is not None and caller_income > scheme["income_max"]:
            return False, [], 0
        if scheme["income_max"] is None:
            clauses.append("no income limit recorded")
        else:
            clauses.append(f"income is within the ₹{scheme['income_max']:,} limit")
        verified += 1

    caller_gender = profile.get("gender")
    if caller_gender is None:
        clauses.append("gender not verified")
    elif scheme["gender"] == "all" or scheme["gender"] == caller_gender:
        if scheme["gender"] == "female":
            clauses.append("for women")
        elif scheme["gender"] == "male":
            clauses.append("for men")
        else:
            clauses.append("open to all genders")
        verified += 1
    else:
        return False, [], 0

    caller_caste = profile.get("caste")
    if caller_caste is None:
        clauses.append("category not verified")
    else:
        if scheme["caste"] and caller_caste not in scheme["caste"]:
            return False, [], 0
        if not scheme["caste"]:
            clauses.append("open to all social categories")
        else:
            clauses.append("for " + "/".join(scheme["caste"]))
        verified += 1

    caller_residence = profile.get("residence")
    if caller_residence is None:
        clauses.append("rural/urban not verified")
    else:
        if scheme["residence"] == "both" or scheme["residence"] == caller_residence:
            if scheme["residence"] == "rural":
                clauses.append("for rural areas")
            elif scheme["residence"] == "urban":
                clauses.append("for urban areas")
            else:
                clauses.append("open to rural and urban areas")
            verified += 1
        else:
            return False, [], 0

    caller_disability = profile.get("disability")
    if caller_disability is None:
        clauses.append("disability status not verified")
    else:
        if scheme["disability"] is True:
            if caller_disability:
                clauses.append("for persons with disability")
                verified += 1
            else:
                return False, [], 0
        else:
            clauses.append("no disability requirement")

    caller_bpl = profile.get("bpl")
    if caller_bpl is None:
        clauses.append("BPL status not verified")
    else:
        if scheme["bpl"] is True:
            if caller_bpl:
                clauses.append("for BPL families")
                verified += 1
            else:
                return False, [], 0
        else:
            clauses.append("no BPL requirement")

    return True, clauses, verified


def _score(scheme: dict[str, Any], profile: dict[str, Any], verified: int) -> int:
    score = verified * 3
    if _is_financial(scheme):
        score += 6
    if _category_relevance(scheme, profile):
        score += 2
    return score


def _match_output(scheme: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "name": scheme["name"],
        "category": scheme["category"],
        "reason": reason,
        "benefits": scheme["benefits"],
        "eligibility_summary": scheme["eligibility_text"],
        "documents_required": scheme["documents_required"],
        "official_url": scheme["official_url"],
        "apply_url": scheme["apply_url"],
        "ministry": scheme["ministry"],
        "state": scheme["state"],
    }


def find_eligible_schemes(
    *,
    age: int | None = None,
    state: str | None = None,
    annual_income: int | None = None,
    gender: str | None = None,
    occupation: str | None = None,
    student: bool | None = None,
    caste: str | None = None,
    residence: str | None = None,
    disability: bool | None = None,
    bpl: bool | None = None,
    _dataset_path: Path | None = None,
) -> dict[str, Any]:
    """Match a caller profile against the local schemes dataset.

    Only facts the caller actually provided should be passed. Missing caller
    facts disable that filter; they are never guessed. Returns a
    JSON-serialisable result dict — never raises.
    """
    logger.info("[SCHEMES] lookup started")
    profile: dict[str, Any] = {}
    if age is not None:
        profile["age"] = _parse_int(age)
    if state:
        profile["state"] = canonical_state(state)
    if annual_income is not None:
        profile["annual_income"] = _parse_int(annual_income)
    gender_value = str(gender).strip().lower() if gender else ""
    if gender_value in ("male", "female"):
        profile["gender"] = gender_value
    if occupation:
        profile["occupation"] = str(occupation).strip()
    if student is not None:
        profile["student"] = _parse_bool(student)
    if caste:
        caste_value = _normalise_caste(str(caste))
        if caste_value is not None:
            profile["caste"] = caste_value
    if residence:
        residence_value = str(residence).strip().lower()
        if residence_value in ("rural", "urban"):
            profile["residence"] = residence_value
    if disability is not None:
        profile["disability"] = _parse_bool(disability)
    if bpl is not None:
        profile["bpl"] = _parse_bool(bpl)

    logger.info("[SCHEMES] profile fields provided: %s", ", ".join(sorted(profile)))

    try:
        records, meta = load_schemes(_dataset_path)
    except SchemeDataError as exc:
        logger.warning("[SCHEMES] dataset unavailable: %s", exc)
        return {
            "status": "error",
            "message": "Scheme data is currently unavailable, so no scheme details can be provided.",
        }
    except Exception as exc:  # pragma: no cover - defensive: never raise
        logger.error("[SCHEMES] unexpected dataset load error: %r", exc)
        return {
            "status": "error",
            "message": "Scheme data is currently unavailable, so no scheme details can be provided.",
        }

    try:
        candidates: list[tuple[int, str, dict[str, Any]]] = []
        for scheme in records:
            eligible, clauses, verified = _evaluate(scheme, profile)
            if not eligible:
                continue
            reason = "; ".join(clauses)
            candidates.append((_score(scheme, profile, verified), reason, scheme))

        candidates.sort(key=lambda item: (-item[0], item[2]["name"].lower()))
        matches = [
            _match_output(scheme, reason)
            for _, reason, scheme in candidates[:MAX_RESULTS]
        ]
    except Exception as exc:  # pragma: no cover - defensive: never raise
        logger.error("[SCHEMES] unexpected matching error: %r", exc)
        return {
            "status": "error",
            "message": "Scheme data is currently unavailable, so no scheme details can be provided.",
        }

    data_as_of = meta.get("data_as_of")
    logger.info("[SCHEMES] matches=%d", len(matches))
    logger.info("[SCHEMES] source=%s", SOURCE)
    logger.info("[SCHEMES] data_as_of=%s", data_as_of)

    result: dict[str, Any] = {
        "status": "success",
        "matches": matches,
        "source": SOURCE,
        "source_url": DATASET_URL,
        "data_as_of": data_as_of,
        "dataset_record_count": meta.get("record_count"),
        "data_note": DATA_NOTE,
        "disclaimer": DISCLAIMER,
    }
    if not matches:
        result["message"] = (
            "No matching schemes were found for the supplied information."
        )
    return result

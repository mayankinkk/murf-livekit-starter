"""Day 5 unit tests for the government scheme eligibility matcher.

These tests use a small fixture CSV (representative records only), so they never
depend on the full 4,693-row dataset. The pure matching logic lives in
``schemes.find_eligible_schemes()``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import schemes


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "slug": "",
        "name": "Test Scheme",
        "description": "",
        "ministry": "Ministry of Finance",
        "department": "",
        "state": "Central",
        "category": "Banking,Financial Services and Insurance",
        "beneficiary_type": "Individual",
        "benefits": "Benefit details.",
        "eligibility_text": "Eligibility details.",
        "application_process": "",
        "documents_required": "1. Aadhaar\n2. Bank account",
        "apply_url": "https://apply.example",
        "official_url": "https://myscheme.gov.in/schemes/test",
        "eligibility_age_min": "null",
        "eligibility_age_max": "null",
        "eligibility_gender": "all",
        "eligibility_caste": "[]",
        "eligibility_income_max": "null",
        "eligibility_residence": "both",
        "eligibility_state": '["All"]',
        "eligibility_disability": "false",
        "eligibility_bpl": "false",
        "scraped_at": "2026-07-05 10:00:00.000+00",
    }
    base.update(overrides)
    return base


def _fixture_rows() -> list[dict[str, object]]:
    return [
        _row(
            name="Pradhan Mantri Jan Dhan Yojana",
            slug="pmjdy",
            official_url="https://myscheme.gov.in/schemes/pmjdy",
        ),
        _row(name="Central Open Scheme", slug="central-open"),
        _row(
            name="Delhi Ladli Scheme",
            slug="delhi-ladli",
            state="Delhi",
            category="Social welfare & Empowerment",
            eligibility_age_min="18",
            eligibility_age_max="60",
            eligibility_gender="female",
            eligibility_income_max="300000",
            eligibility_state='["Delhi"]',
        ),
        _row(
            name="Gujarat State Scheme",
            slug="guj-scheme",
            state="Gujarat",
            category="Social welfare & Empowerment",
            eligibility_state='["Gujarat"]',
        ),
        _row(
            name="Sukanya Samriddhi Yojana",
            slug="sukanya",
            eligibility_age_max="10",
            eligibility_gender="female",
        ),
        _row(
            name="Old Age Pension",
            slug="oap",
            eligibility_age_min="60",
            eligibility_income_max="100000",
            eligibility_bpl="true",
        ),
        _row(
            name="Ambedkar Scholarship",
            slug="scholar",
            category="Education & Learning",
            eligibility_age_min="18",
            eligibility_age_max="25",
            eligibility_caste='["SC"]',
        ),
        _row(
            name="Rural Housing Scheme",
            slug="rural-housing",
            eligibility_residence="rural",
            eligibility_income_max="300000",
        ),
        _row(name="Men Only Scheme", slug="men-only", eligibility_gender="male"),
        _row(
            name="BPL Ration Scheme",
            slug="bpl-ration",
            eligibility_bpl="true",
            eligibility_income_max="200000",
        ),
    ]


def _write_fixture(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    header = [*schemes.REQUIRED_COLUMNS, "slug", "description", "beneficiary_type"]
    path = tmp_path / "Schemes.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _match_names(result: dict) -> list[str]:
    return [m["name"] for m in result.get("matches", [])]


def test_valid_profile_returns_matching_schemes(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    result = schemes.find_eligible_schemes(
        _dataset_path=path,
        age=20,
        state="Delhi",
        annual_income=250000,
        gender="female",
        student=True,
    )
    assert result["status"] == "success"
    names = _match_names(result)
    assert "Pradhan Mantri Jan Dhan Yojana" in names
    assert "Delhi Ladli Scheme" in names
    assert "Gujarat State Scheme" not in names
    assert "Men Only Scheme" not in names
    assert result["matches"], "expected at least one match"


def test_state_matching_works(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    delhi = schemes.find_eligible_schemes(_dataset_path=path, state="Delhi", age=30)
    delhi_names = _match_names(delhi)
    assert "Delhi Ladli Scheme" in delhi_names

    karnataka = schemes.find_eligible_schemes(
        _dataset_path=path, state="Karnataka", age=30
    )
    karnataka_names = _match_names(karnataka)
    assert "Delhi Ladli Scheme" not in karnataka_names
    assert "Gujarat State Scheme" not in karnataka_names


def test_age_matching_works(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    child = schemes.find_eligible_schemes(_dataset_path=path, age=8, gender="female")
    assert "Sukanya Samriddhi Yojana" in _match_names(child)

    teen = schemes.find_eligible_schemes(_dataset_path=path, age=14, gender="female")
    assert "Sukanya Samriddhi Yojana" not in _match_names(teen)

    senior = schemes.find_eligible_schemes(
        _dataset_path=path, age=70, annual_income=80000, bpl=True
    )
    assert "Old Age Pension" in _match_names(senior)

    young = schemes.find_eligible_schemes(_dataset_path=path, age=30)
    assert "Old Age Pension" not in _match_names(young)


def test_income_matching_works(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    high = schemes.find_eligible_schemes(
        _dataset_path=path, state="Delhi", gender="female", age=30, annual_income=600000
    )
    assert "Delhi Ladli Scheme" not in _match_names(high)

    low = schemes.find_eligible_schemes(
        _dataset_path=path, state="Delhi", gender="female", age=30, annual_income=200000
    )
    assert "Delhi Ladli Scheme" in _match_names(low)


def test_central_schemes_match_any_state(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    for state in ("Delhi", "Karnataka", "Himachal Pradesh"):
        result = schemes.find_eligible_schemes(_dataset_path=path, state=state, age=30)
        assert "Pradhan Mantri Jan Dhan Yojana" in _match_names(result)
        assert "Central Open Scheme" in _match_names(result)


def test_irrelevant_state_schemes_not_returned(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    result = schemes.find_eligible_schemes(
        _dataset_path=path, state="Delhi", age=30, gender="male"
    )
    assert "Gujarat State Scheme" not in _match_names(result)


def test_missing_optional_fields_do_not_crash(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    result = schemes.find_eligible_schemes(_dataset_path=path, age=20)
    assert result["status"] == "success"
    names = _match_names(result)
    assert "Pradhan Mantri Jan Dhan Yojana" in names
    assert "Gujarat State Scheme" not in names


def test_no_matches_returns_clean_empty_result(tmp_path) -> None:
    rows = [
        _row(
            name="Delhi Women Only",
            state="Delhi",
            eligibility_gender="female",
            eligibility_state='["Delhi"]',
        )
    ]
    path = _write_fixture(tmp_path, rows)
    result = schemes.find_eligible_schemes(
        _dataset_path=path, state="Delhi", gender="male", age=30
    )
    assert result["status"] == "success"
    assert result["matches"] == []
    assert "No matching schemes" in result.get("message", "")


def test_missing_csv_returns_controlled_error(tmp_path) -> None:
    missing = tmp_path / "does-not-exist.csv"
    result = schemes.find_eligible_schemes(_dataset_path=missing, age=20, state="Delhi")
    assert result["status"] == "error"
    assert "currently unavailable" in result["message"]


def test_malformed_csv_returns_controlled_error(tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("name,foo\nBar,1\n", encoding="utf-8")
    result = schemes.find_eligible_schemes(_dataset_path=bad, age=20)
    assert result["status"] == "error"
    assert "currently unavailable" in result["message"]

    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    result = schemes.find_eligible_schemes(_dataset_path=empty, age=20)
    assert result["status"] == "error"


def test_results_include_source_and_date(tmp_path) -> None:
    rows = _fixture_rows()
    rows[0] = _row(
        name="Pradhan Mantri Jan Dhan Yojana",
        slug="pmjdy",
        scraped_at="2026-07-06 08:30:00.000+00",
    )
    path = _write_fixture(tmp_path, rows)
    result = schemes.find_eligible_schemes(_dataset_path=path, age=20, state="Delhi")
    assert result["status"] == "success"
    assert "source" in result and "dataset" in result["source"].lower()
    assert result["source_url"].startswith("https://huggingface.co")
    assert result["data_as_of"] == "2026-07-06"
    assert result["dataset_record_count"] == len(rows)
    assert "disclaimer" in result and "preliminary" in result["disclaimer"].lower()
    assert result["matches"], "expected matches"
    first = result["matches"][0]
    assert first["official_url"] or first["apply_url"]


def test_tool_output_is_valid_json(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())
    result = schemes.find_eligible_schemes(_dataset_path=path, age=20, state="Delhi")
    encoded = json.dumps(result, ensure_ascii=False)
    decoded = json.loads(encoded)
    assert decoded["status"] == "success"
    assert isinstance(decoded["matches"], list)


def test_canonical_state_mapping() -> None:
    assert schemes.canonical_state("Delhi") == "Delhi"
    assert schemes.canonical_state("New Delhi") == "Delhi"
    assert schemes.canonical_state("pondicherry") == "Puducherry"
    assert schemes.canonical_state("Tamil Nadu") == "Tamil Nadu"
    assert schemes.canonical_state("UP") == "Uttar Pradesh"
    assert schemes.canonical_state("unknown land") is None
    assert schemes.canonical_state("") is None


def test_gender_residence_caste_bpl_matching(tmp_path) -> None:
    path = _write_fixture(tmp_path, _fixture_rows())

    urban = schemes.find_eligible_schemes(
        _dataset_path=path, age=30, residence="urban", annual_income=200000
    )
    assert "Rural Housing Scheme" not in _match_names(urban)

    rural = schemes.find_eligible_schemes(
        _dataset_path=path, age=30, residence="rural", annual_income=200000
    )
    assert "Rural Housing Scheme" in _match_names(rural)

    sc = schemes.find_eligible_schemes(
        _dataset_path=path, age=20, caste="SC", student=True
    )
    assert "Ambedkar Scholarship" in _match_names(sc)

    general = schemes.find_eligible_schemes(
        _dataset_path=path, age=20, caste="General", student=True
    )
    assert "Ambedkar Scholarship" not in _match_names(general)

    non_bpl = schemes.find_eligible_schemes(_dataset_path=path, age=70, bpl=False)
    assert "Old Age Pension" not in _match_names(non_bpl)

    bpl = schemes.find_eligible_schemes(
        _dataset_path=path, age=70, bpl=True, annual_income=80000
    )
    assert "Old Age Pension" in _match_names(bpl)

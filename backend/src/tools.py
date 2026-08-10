"""
tools.py — Day 5: Real-data function tools for BharatPay Pooja Voice Agent

Three tools that fetch or compute real domain data:

1. get_usd_inr_rate()
   → Fetches LIVE USD/INR exchange rate from open.er-api.com (no API key needed).
   → Falls back to last known rate with a clear disclaimer if the API is unreachable.
   → The agent should state the timestamp so users know exactly how fresh the data is.

2. get_lending_rates()
   → Returns the current RBI Repo Rate + BharatPay personal loan APR range.
   → Sourced from hand-built local dataset (curated from RBI press releases).
   → Always tells the agent when the data was last verified.

3. check_scheme_eligibility(age, has_bank_account, is_msme_owner, is_tax_payer)
   → Checks a user against the eligibility rules for 5 key government financial schemes.
   → Entirely local computation — no network needed; never fails.
   → Returns a spoken-friendly list of matching schemes with brief benefit summaries.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger("agent.tools")

# ---------------------------------------------------------------------------
# Path to the hand-built local dataset
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SCHEMES_PATH = os.path.join(_DATA_DIR, "schemes.json")

# Load once at import time
with open(_SCHEMES_PATH, encoding="utf-8") as _f:
    _LOCAL_DATA: dict[str, Any] = json.load(_f)


# ---------------------------------------------------------------------------
# Helper — fetch USD/INR from open.er-api.com
# ---------------------------------------------------------------------------

_ER_API_URL = "https://open.er-api.com/v6/latest/USD"
_FALLBACK_INR_RATE = 84.0  # Last known approximate value — update periodically
_FALLBACK_RATE_DATE = "2025-10-01"  # When this fallback was set


async def _fetch_usd_inr() -> dict[str, Any]:
    """
    Try to get a live USD→INR rate.  Returns a dict with:
        inr_per_usd   float    — the exchange rate
        as_of         str      — human-readable timestamp
        is_live       bool     — True if from the live API, False if fallback
        error_hint    str|None — set only when using fallback
    """
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(_ER_API_URL) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        if data.get("result") != "success":
            raise ValueError("API returned non-success")

        return {
            "inr_per_usd": round(data["rates"]["INR"], 4),
            "as_of": data.get("time_last_update_utc", "unknown"),
            "is_live": True,
            "error_hint": None,
        }

    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as exc:
        logger.warning("USD/INR live fetch failed: %s — using fallback", exc)
        return {
            "inr_per_usd": _FALLBACK_INR_RATE,
            "as_of": _FALLBACK_RATE_DATE,
            "is_live": False,
            "error_hint": (
                "Live rate service is currently unreachable. "
                f"Showing last known rate from {_FALLBACK_RATE_DATE}."
            ),
        }


# ===========================================================================
# TOOL 1 — USD / INR Exchange Rate
# ===========================================================================

async def get_usd_inr_rate_impl() -> str:
    """
    Fetches the current USD to INR exchange rate.
    Always includes the data freshness timestamp in the result.
    """
    rate_data = await _fetch_usd_inr()
    inr = rate_data["inr_per_usd"]
    as_of = rate_data["as_of"]
    is_live = rate_data["is_live"]

    if is_live:
        result = {
            "status": "live",
            "inr_per_usd": inr,
            "data_as_of": as_of,
            "spoken_summary": (
                f"As of {as_of}, one US dollar equals {inr:.2f} Indian rupees. "
                f"This is today's live rate from the exchange rate service."
            ),
        }
    else:
        result = {
            "status": "fallback",
            "inr_per_usd": inr,
            "data_as_of": as_of,
            "warning": rate_data["error_hint"],
            "spoken_summary": (
                f"I was unable to reach the live exchange rate service right now. "
                f"The last rate I have on file from {as_of} was approximately {inr:.0f} rupees per US dollar. "
                f"For the exact current rate, please check your bank app or RBI's website."
            ),
        }

    logger.info("get_usd_inr_rate → status=%s  inr=%s  as_of=%s", result["status"], inr, as_of)
    return json.dumps(result)


# ===========================================================================
# TOOL 2 — Current Lending Rates (RBI Repo + BharatPay Loan APR)
# ===========================================================================

def get_lending_rates_impl() -> str:
    """
    Returns the current RBI Repo Rate and BharatPay personal loan rate range.
    Data sourced from the hand-built local dataset (compiled from RBI press releases).
    Always states when the data was last verified.
    """
    rbi = _LOCAL_DATA["rbi_rates"]
    bp_loan = _LOCAL_DATA["bharatpay_loan"]
    meta = _LOCAL_DATA["_meta"]

    repo = rbi["repo_rate_pct"]
    rev_repo = rbi["reverse_repo_rate_pct"]
    eff_date = rbi["effective_date"]
    loan_min = bp_loan["min_apr_pct"]
    loan_max = bp_loan["max_apr_pct"]
    loan_min_amt = bp_loan["min_amount_inr"]
    loan_max_amt = bp_loan["max_amount_inr"]
    loan_proc_fee = bp_loan["processing_fee_pct"]
    docs = bp_loan["documents_needed"]
    tat = bp_loan["turnaround_hours"]
    last_verified = meta["last_verified"]

    result = {
        "status": "local_dataset",
        "data_source": "Hand-built dataset — compiled from RBI press releases",
        "last_verified": last_verified,
        "rbi_repo_rate_pct": repo,
        "rbi_reverse_repo_rate_pct": rev_repo,
        "rbi_rate_effective_date": eff_date,
        "bharatpay_loan_apr_range": f"{loan_min}%–{loan_max}%",
        "bharatpay_loan_amount_range_inr": f"₹{loan_min_amt:,}–₹{loan_max_amt:,}",
        "bharatpay_loan_processing_fee_pct": loan_proc_fee,
        "documents_needed": docs,
        "decision_turnaround": f"{tat} hours",
        "spoken_summary": (
            f"As of {eff_date}, the RBI Repo Rate is {repo} percent. "
            f"BharatPay personal loans are offered between {loan_min} percent and {loan_max} percent annual interest, "
            f"for amounts from {loan_min_amt:,} to {loan_max_amt:,} rupees. "
            f"There is a {loan_proc_fee} percent processing fee. "
            f"You will need your Aadhaar, PAN, last 3 months bank statement, and income proof. "
            f"The decision typically comes within {tat} hours of document submission. "
            f"This data was last verified on {last_verified}."
        ),
    }

    logger.info("get_lending_rates → repo_rate=%s%%  bp_apr=%s%%–%s%%  as_of=%s", repo, loan_min, loan_max, last_verified)
    return json.dumps(result)


# ===========================================================================
# TOOL 3 — Government Scheme Eligibility Checker
# ===========================================================================

def check_scheme_eligibility_impl(
    age: int,
    has_bank_account: bool,
    is_msme_owner: bool = False,
    is_income_tax_payer: bool = False,
) -> str:
    """
    Checks a caller against eligibility rules for key Indian government financial schemes.
    Pure local computation — no external API needed; never fails.

    Returns a list of schemes the caller likely qualifies for,
    with a brief benefit summary for each.
    """
    schemes = _LOCAL_DATA["government_schemes"]
    eligible: list[dict] = []

    for scheme in schemes:
        sid = scheme["id"]
        qualified = False
        reason = ""

        if sid == "pmmy":
            # PM Mudra Yojana: MSME owner, age 18–65
            if is_msme_owner and 18 <= age <= 65:
                qualified = True
                reason = f"You can get a business loan up to {scheme['max_loan_inr']:,} rupees."

        elif sid == "pmjdy":
            # Jan Dhan: Any Indian citizen
            qualified = True
            reason = "Zero-balance savings account with ₹2 lakh accidental insurance and ₹10,000 overdraft facility."

        elif sid == "pmsby":
            # PMSBY: Age 18–70, has bank account
            if has_bank_account and 18 <= age <= 70:
                qualified = True
                reason = f"Accident insurance of {scheme['coverage_inr']:,} rupees for just {scheme['annual_premium_inr']} rupees per year."

        elif sid == "pmjjby":
            # PMJJBY: Age 18–50, has bank account
            if has_bank_account and 18 <= age <= 50:
                qualified = True
                reason = f"Life insurance of {scheme['coverage_inr']:,} rupees for {scheme['annual_premium_inr']} rupees per year."

        elif sid == "apy":
            # APY: Age 18–40, NOT an income tax payer
            if has_bank_account and 18 <= age <= 40 and not is_income_tax_payer:
                qualified = True
                reason = "Guaranteed pension of 1,000 to 5,000 rupees per month after age 60."

        if qualified:
            eligible.append({
                "scheme_id": sid,
                "scheme_name": scheme["name"],
                "category": scheme["category"],
                "why_eligible": reason,
            })

    as_of = _LOCAL_DATA["_meta"]["last_verified"]

    if eligible:
        names = ", ".join(s["scheme_name"] for s in eligible)
        spoken = (
            f"Based on the details you've shared, you appear to be eligible for {len(eligible)} scheme{'s' if len(eligible) > 1 else ''}. "
            + " ".join(
                f"{s['scheme_name']}: {s['why_eligible']}"
                for s in eligible
            )
            + f" These scheme details are based on government guidelines last verified on {as_of}. "
            f"For final confirmation and enrollment, please visit your nearest bank branch or BharatPay app."
        )
    else:
        spoken = (
            "Based on the information you've shared, I wasn't able to identify a specific scheme that matches all your criteria right now. "
            "This doesn't mean you're not eligible — I'd recommend visiting myscheme.gov.in or your nearest bank branch for a comprehensive check."
        )

    result = {
        "status": "ok",
        "eligible_schemes": eligible,
        "total_matches": len(eligible),
        "data_source": "Hand-built local dataset — compiled from government scheme guidelines",
        "data_as_of": as_of,
        "spoken_summary": spoken,
    }

    logger.info(
        "check_scheme_eligibility → age=%s  bank=%s  msme=%s  taxpayer=%s  matches=%s",
        age, has_bank_account, is_msme_owner, is_income_tax_payer, len(eligible),
    )
    return json.dumps(result)

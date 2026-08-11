"""Download the Day 5 schemes dataset (Schemes.csv) into backend/data/.

Dataset: "Indian Government Schemes 2025" by SmartDuke Technologies (CC BY 4.0),
derived from India's myScheme portal (https://www.myscheme.gov.in/).
Source: https://huggingface.co/datasets/smartduketech/indian-government-schemes-2025

Run from the backend directory:

    uv run python scripts/fetch_schemes.py

Only stdlib is used, so no new dependencies are required.
"""

from __future__ import annotations

import pathlib
import urllib.request

DATASET_URL = (
    "https://huggingface.co/datasets/smartduketech/"
    "indian-government-schemes-2025/resolve/main/Schemes.csv?download=true"
)
TARGET = pathlib.Path(__file__).resolve().parent.parent / "data" / "Schemes.csv"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Schemes.csv to {TARGET} ...")
    request = urllib.request.Request(
        DATASET_URL, headers={"User-Agent": "murf-rupeegpt-day5/1.0"}
    )
    with urllib.request.urlopen(request) as response, open(TARGET, "wb") as out:
        while True:
            chunk = response.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
    size_mb = TARGET.stat().st_size / (1024 * 1024)
    print(f"Done: {TARGET} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

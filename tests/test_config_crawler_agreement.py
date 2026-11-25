"""Guards that sample company selector keys match the keys the crawler reads."""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "companies.json"

CRAWLER_SELECTOR_KEYS = {
    "job_container",
    "title",
    "location",
    "link",
    "description_selector",
    "inner_description_selector",
    "requirements_selector",
}


def _load_companies() -> dict[str, dict]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        companies: dict[str, dict] = json.load(f)["companies"]
    return companies


def test_config_has_at_least_one_company() -> None:
    assert _load_companies()


def test_every_selector_key_is_read_by_crawler() -> None:
    for name, company in _load_companies().items():
        unknown = set(company.get("selectors", {})) - CRAWLER_SELECTOR_KEYS
        assert not unknown, f"{name} has selector keys the crawler ignores: {sorted(unknown)}"

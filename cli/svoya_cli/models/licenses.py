"""License awareness: may *you* use this model, here, for this purpose?

Order of evidence: the curated catalog (``data/model_catalog.toml``, matched on repo/file names)
→ the license id from GGUF metadata (``general.license``) or the Hub model card → unknown.
Region and purpose come from ``~/.config/svoya/svoya.toml`` ``[models] region = "EU"``,
``commercial = true`` (the strict default: commercial use in the EU).
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import tr

# Generic license ids (SPDX / Hub ids, lowercase) → (display, commercial, attribution, excluded regions)
LICENSES: dict[str, tuple[str, object, bool, tuple[str, ...]]] = {
    "apache-2.0": ("Apache-2.0", True, False, ()),
    "mit": ("MIT", True, False, ()),
    "bsd-2-clause": ("BSD-2-Clause", True, False, ()),
    "bsd-3-clause": ("BSD-3-Clause", True, False, ()),
    "cc0-1.0": ("CC0-1.0", True, False, ()),
    "unlicense": ("Unlicense", True, False, ()),
    "cc-by-4.0": ("CC-BY-4.0", True, True, ()),
    "cc-by-sa-4.0": ("CC-BY-SA-4.0", True, True, ()),
    "cc-by-nc-4.0": ("CC-BY-NC-4.0", False, True, ()),
    "cc-by-nc-sa-4.0": ("CC-BY-NC-SA-4.0", False, True, ()),
    "cc-by-nc-nd-4.0": ("CC-BY-NC-ND-4.0", False, True, ()),
    "openrail": ("OpenRAIL", "conditional", False, ()),
    "openrail++": ("OpenRAIL++", "conditional", False, ()),
    "creativeml-openrail-m": ("CreativeML OpenRAIL-M", "conditional", False, ()),
    "gemma": ("Gemma Terms of Use", "conditional", False, ()),
    "llama3": ("Llama 3 Community", "conditional", True, ()),
    "llama3.1": ("Llama 3.1 Community", "conditional", True, ()),
    "llama3.2": ("Llama 3.2 Community", "conditional", True, ()),
    "llama3.3": ("Llama 3.3 Community", "conditional", True, ()),
    "llama4": ("Llama 4 Community", "conditional", True, ()),
    "flux-1-dev-non-commercial-license": ("FLUX.1 [dev] non-commercial", False, False, ()),
    "qwen-research": ("Qwen Research (non-commercial)", False, False, ()),
    "tencent-hunyuan-community": ("Tencent Hunyuan Community", "conditional", False, ("EU", "UK", "KR")),
}


@dataclass
class Verdict:
    license: str | None
    commercial: object = None             # True | False | "conditional" | None (unknown)
    excluded: tuple[str, ...] = ()
    excluded_multimodal: tuple[str, ...] = ()
    attribution: bool = False
    catalog_id: str | None = None
    kind: str | None = None
    note: dict = field(default_factory=dict)

    def allows(self, region: str = "EU", commercial: bool = True, multimodal: bool = False) -> tuple[str, str]:
        """→ (status, reason): status ok | warn | no."""
        region = region.upper()
        if region in self.excluded:
            return "no", tr(f"license excludes the {region}", f"лицензия не для {_region_ru(region)}")
        if multimodal and region in self.excluded_multimodal:
            return "no", tr(f"multimodal use excluded in the {region}", f"мультимодальность не для {_region_ru(region)}")
        if commercial and self.commercial is False:
            return "no", tr("non-commercial license", "некоммерческая лицензия")
        if self.license is None and self.commercial is None:
            return "warn", tr("license unknown — check the model card", "лицензия неизвестна — проверьте карточку модели")
        if self.commercial is None:
            return "warn", tr(f"{self.license}: terms not in svoya's table — check them",
                              f"{self.license}: условий нет в таблице svoya — проверьте")
        if self.excluded_multimodal and region in self.excluded_multimodal and not multimodal:
            return "warn", tr("text only in your region (vision excluded)", "в вашем регионе — только текст (без зрения)")
        if commercial and self.commercial == "conditional":
            return "warn", tr("commercial use with conditions", "коммерция с условиями")
        if self.attribution:
            return "ok", tr("attribution required", "нужна атрибуция")
        return "ok", ""

    def as_json(self) -> dict:
        return {"license": self.license, "commercial": self.commercial, "excludedRegions": list(self.excluded),
                "excludedRegionsMultimodal": list(self.excluded_multimodal), "attribution": self.attribution,
                "catalogId": self.catalog_id}


def _region_ru(r: str) -> str:
    return {"EU": "ЕС", "UK": "Великобритании", "US": "США", "KR": "Южной Кореи"}.get(r, r)


_catalog_cache: list[dict] | None = None


def catalog(data_dir: Path | None = None) -> list[dict]:
    global _catalog_cache
    if _catalog_cache is None or data_dir is not None:
        base = data_dir or Path(__file__).resolve().parent.parent / "data"
        with open(base / "model_catalog.toml", "rb") as f:
            _catalog_cache = tomllib.load(f).get("model", [])
    return _catalog_cache


def from_catalog(entry: dict) -> Verdict:
    return Verdict(license=entry.get("license"), commercial=entry.get("commercial"),
                   excluded=tuple(entry.get("excluded", [])),
                   excluded_multimodal=tuple(entry.get("excluded_multimodal", [])),
                   attribution=bool(entry.get("attribution")), catalog_id=entry.get("id"),
                   kind=entry.get("kind"), note=entry.get("note") or {})


def match_catalog(text: str) -> dict | None:
    t = text.lower()
    for e in catalog():
        if any(m in t for m in e.get("match", [])):
            return e
    return None


def classify(*, repo: str | None = None, filename: str | None = None, license_id: str | None = None) -> Verdict:
    hay = "/".join(x for x in (repo, filename) if x)
    if hay:
        e = match_catalog(hay)
        if e:
            return from_catalog(e)
    if license_id:
        lid = license_id.strip().lower()
        hit = LICENSES.get(lid)
        if hit:
            name, com, attr, excl = hit
            return Verdict(license=name, commercial=com, attribution=attr, excluded=excl)
        if lid in ("other", "unknown", ""):
            return Verdict(license=None)
        return Verdict(license=license_id, commercial=None)
    return Verdict(license=None)

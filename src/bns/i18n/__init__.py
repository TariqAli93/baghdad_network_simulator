"""Arabic / English translations for the application and the printable report.

Strings live in YAML files per feature: `locales/<lang>/<feature>.yaml`. A key is
`<feature>.<path>`, e.g. `dashboard.title`. Use one translator per language:

    tr = translator("ar")
    tr("dashboard.study_area")                       # plain text
    tr("simulation.traced", done=3, total=15)        # interpolation with str.format fields
    tr("dashboard.sites", count=4)                   # plural forms (zero/one/two/few/many/other)

Missing keys fall back to English, then to the key itself (never an exception). Internal
identifiers, configuration keys, file names and data fields are never translated. Numbers keep
Western digits in both languages (scientific values stay unambiguous); dates use localized
month names. `validate()` reports keys missing in a language and placeholder mismatches.
"""

from __future__ import annotations

import re
import string
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml

LOCALES = Path(__file__).resolve().parent / "locales"
LANGUAGES = ("ar", "en")
DEFAULT = "ar"
FALLBACK = "en"
RTL = {"ar"}
_MONTHS_AR = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
              "نوفمبر", "ديسمبر")
_PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")


def _flatten(prefix: str, data, out: dict) -> None:
    if isinstance(data, dict) and not (set(data) and set(data) <= set(_PLURAL_FORMS)):
        for k, v in data.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out[prefix] = data


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict:
    """All strings of a language, flattened to dotted keys (plural entries stay dicts)."""
    out: dict = {}
    for path in sorted((LOCALES / lang).glob("*.yaml")):
        _flatten(path.stem, yaml.safe_load(path.read_text(encoding="utf-8")) or {}, out)
    return out


def plural_form(lang: str, n: float) -> str:
    """CLDR plural category: Arabic has six, English two."""
    if lang == "ar":
        n = abs(int(n)) if float(n).is_integer() else n
        if not isinstance(n, int):
            return "other"
        if n == 0:
            return "zero"
        if n == 1:
            return "one"
        if n == 2:
            return "two"
        if 3 <= n % 100 <= 10:
            return "few"
        if 11 <= n % 100 <= 99:
            return "many"
        return "other"
    return "one" if n == 1 else "other"


def _pick(entry, lang: str, count):
    if isinstance(entry, dict):
        form = plural_form(lang, count if count is not None else 0)
        return entry.get(form) or entry.get("other") or next(iter(entry.values()))
    return entry


def translate(lang: str, key: str, count=None, **values) -> str:
    lang = lang if lang in LANGUAGES else FALLBACK
    entry = catalog(lang).get(key)
    used = lang
    if entry is None:
        entry, used = catalog(FALLBACK).get(key), FALLBACK
    if entry is None:
        return key
    text = str(_pick(entry, used, count))
    if count is not None:
        values.setdefault("count", count)
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return text


class Translator:
    def __init__(self, lang: str):
        self.lang = lang if lang in LANGUAGES else DEFAULT

    def __call__(self, key: str, count=None, **values) -> str:
        return translate(self.lang, key, count, **values)

    @property
    def rtl(self) -> bool:
        return self.lang in RTL

    @property
    def direction(self) -> str:
        return "rtl" if self.rtl else "ltr"

    def has(self, key: str) -> bool:
        return key in catalog(self.lang) or key in catalog(FALLBACK)

    def date(self, value) -> str:
        """'27 November 2026, 01:31' / '27 نوفمبر 2026، 01:31' from a datetime or ISO string (UTC kept)."""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        if self.lang == "ar":
            return f"{value.day} {_MONTHS_AR[value.month - 1]} {value.year}، {value:%H:%M}"
        return f"{value.day} {value:%B %Y}, {value:%H:%M}"

    def number(self, value, spec: str = ".1f", unit: str = "", scale: float = 1.0) -> str:
        """A number with its unit; '—' when missing. Western digits in both languages."""
        try:
            v = float(value) * scale
        except (TypeError, ValueError):
            return "—"
        if v != v or v in (float("inf"), float("-inf")):
            return "—"
        return f"{v:{spec}}{unit}"


def translator(lang: str) -> Translator:
    return Translator(lang)


def _fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def validate() -> dict:
    """{'missing': {lang: [keys]}, 'placeholders': [(key, lang, fields)], 'plural': [...]} against English."""
    en = catalog(FALLBACK)
    report = {"missing": {}, "placeholders": [], "extra": {}}
    for lang in LANGUAGES:
        cat = catalog(lang)
        report["missing"][lang] = sorted(k for k in en if k not in cat)
        report["extra"][lang] = sorted(k for k in cat if k not in en)
        for key, entry in cat.items():
            if key not in en:
                continue
            ref = en[key]
            ref_fields = set().union(*(_fields(str(v)) for v in (ref.values() if isinstance(ref, dict) else [ref])))
            mine = set().union(*(_fields(str(v)) for v in (entry.values() if isinstance(entry, dict) else [entry])))
            if mine - ref_fields - {"count"}:
                report["placeholders"].append((key, lang, sorted(mine - ref_fields)))
    return report


KEY_PATTERN = re.compile(r"""\bt\(\s*["']([a-z0-9_]+(?:\.[a-z0-9_]+)+)["']""")


_DEVIATIONS = (
    (re.compile(r"^(?P<name>\S+) profile \((?P<cell>[\d.]+) m, (?P<rays>\S+) rays\)$"), "cls.dev_profile"),
    (re.compile(r"^(?P<backend>\w+) backend \(numerical limits: (?P<doc>.+)\)$"), "cls.dev_backend"),
)


def deviation_text(tr: Translator, text: str) -> str:
    """A recorded deviation (bns.simulation.experiment.baseline_deviations; stored in English in the
    manifest) in the translator's language; parameter overrides ('name = value') stay as recorded."""
    for pattern, key in _DEVIATIONS:
        m = pattern.match(text)
        if m:
            return tr(key, **m.groupdict())
    return text


def classification_names(tr: Translator, c) -> tuple[str, str, str, str]:
    """(result, configuration, dataset, validation) of a Classification, each in the translator's language."""
    from bns.analysis import classification as cl

    head, _ = classification_texts(tr, c)
    term = {cl.BASELINE: "cls.baseline", cl.CUSTOM: "cls.custom", cl.SENSITIVITY: "cls.sensitivity",
            cl.NOT_RECORDED: "cls.not_recorded", cl.COMPLETE: "cls.complete", cl.ESTIMATED: "cls.estimated",
            cl.INCOMPLETE: "cls.incomplete", cl.VALIDATED: "cls.validated", cl.PENDING: "cls.pending"}
    return head, *(tr(term[v]) if v in term else v for v in (c.configuration, c.dataset, c.validation))


def classification_texts(tr: Translator, c) -> tuple[str, str]:
    """(headline, details) of a bns.analysis.classification.Classification in the translator's language."""
    from bns.analysis import classification as cl

    term = {cl.BASELINE: "cls.baseline", cl.CUSTOM: "cls.custom", cl.SENSITIVITY: "cls.sensitivity",
            cl.NOT_RECORDED: "cls.not_recorded", cl.COMPLETE: "cls.complete", cl.ESTIMATED: "cls.estimated",
            cl.INCOMPLETE: "cls.incomplete", cl.VALIDATED: "cls.validated", cl.PENDING: "cls.pending",
            cl.PRELIMINARY: "cls.preliminary", cl.VALIDATED_RESULTS: "cls.validated_results",
            cl.SIMULATION_RESULTS: "cls.simulation_results", f"{cl.BASELINE} · {cl.PENDING}": "cls.baseline_pending"}

    def name(value: str) -> str:
        return tr(term[value]) if value in term else value

    config = name(c.configuration)
    if c.deviations:
        config += f" ({'; '.join(deviation_text(tr, d) for d in c.deviations)})"
    details = tr("cls.details", configuration=config, dataset=name(c.dataset),
                 validation=tr("cls.validation_short.completed" if c.validation == cl.VALIDATED
                               else "cls.validation_short.pending"))
    return name(c.result), details


def classification_explanation(tr: Translator, c) -> str:
    """One sentence on what the result class means."""
    from bns.analysis import classification as cl

    key = {cl.PRELIMINARY: "preliminary", cl.SIMULATION_RESULTS: "simulation_results", cl.CUSTOM: "custom",
           cl.SENSITIVITY: "sensitivity", cl.VALIDATED_RESULTS: "validated_results"}.get(c.result, "baseline_pending")
    return tr(f"cls.explain.{key}")

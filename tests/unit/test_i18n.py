"""Arabic/English translations: completeness, plural rules, fallback, terminology, report direction."""

import json
import re
from pathlib import Path

import pytest
import yaml

from bns import i18n

ROOT = Path(__file__).resolve().parents[2]
ARABIC = re.compile(r"[؀-ۿ]")


def test_both_languages_have_the_same_keys_and_placeholders():
    report = i18n.validate()
    assert report["missing"] == {"ar": [], "en": []}
    assert report["extra"] == {"ar": [], "en": []}
    assert report["placeholders"] == []


def test_every_literal_key_used_by_the_app_exists():
    used = set()
    for path in [*(ROOT / "app").rglob("*.py"), *(ROOT / "src" / "bns").rglob("*.py")]:
        used |= set(i18n.KEY_PATTERN.findall(path.read_text(encoding="utf-8")))
    assert used, "the scan finds the t() calls"
    for lang in i18n.LANGUAGES:
        assert sorted(k for k in used if k not in i18n.catalog(lang)) == [], lang


def test_every_arabic_string_is_translated_not_copied_english():
    """Arabic entries contain Arabic script, except pure identifiers, units and acronyms."""
    copied = []
    for key, entry in i18n.catalog("ar").items():
        for text in (entry.values() if isinstance(entry, dict) else [entry]):
            text = str(text)
            words = re.findall(r"[A-Za-z]{4,}", re.sub(r"\{[^}]*\}|`[^`]*`|\S+\.(md|py|yaml|json)\S*", "", text))
            if text and not ARABIC.search(text) and len(words) >= 3:
                copied.append(key)
    assert copied == []


@pytest.mark.parametrize(("n", "form"), [(0, "zero"), (1, "one"), (2, "two"), (3, "few"), (10, "few"),
                                         (11, "many"), (99, "many"), (100, "other"), (102, "other"), (103, "few")])
def test_arabic_plural_categories(n, form):
    assert i18n.plural_form("ar", n) == form        # CLDR: 'few' for n % 100 in 3..10, 'many' for 11..99


def test_plurals_and_interpolation():
    assert i18n.translate("en", "common.sites", count=1) == "1 site"
    assert i18n.translate("en", "common.sites", count=4) == "4 sites"
    assert i18n.translate("ar", "common.sites", count=2) != i18n.translate("ar", "common.sites", count=5)
    assert "3" in i18n.translate("ar", "simulation.history.traced", done=3, total=15)
    assert "15" in i18n.translate("ar", "simulation.history.traced", done=3, total=15)


def test_fallback_to_english_then_to_the_key():
    assert i18n.translate("fr", "nav.dashboard") == i18n.translate("en", "nav.dashboard")
    assert i18n.translate("ar", "no.such.key") == "no.such.key"


def test_dates_are_localized_and_numbers_keep_western_digits():
    ar = i18n.translator("ar")
    assert ar.date("2026-11-27T01:31:03+00:00") == "27 نوفمبر 2026، 01:31"
    assert i18n.translator("en").date("2026-11-27T01:31:03+00:00") == "27 November 2026, 01:31"
    assert ar.number(0.5, ".1%") == "50.0%" and ar.number(None) == "—"
    assert ar.rtl and ar.direction == "rtl" and not i18n.translator("en").rtl


@pytest.mark.parametrize(("key", "arabic"), [
    ("nav.study_area", "منطقة الدراسة"), ("nav.dashboard", "لوحة المعلومات"), ("nav.run_simulation", "تشغيل المحاكاة"),
    ("nav.coverage", "تحليل التغطية"), ("coverage.layers.rx_power_dbm", "قدرة الإشارة المستقبلة"),
    ("nav.planning", "تخطيط مواقع المحطات"), ("cls.baseline", "الإعدادات البحثية الأساسية"),
    ("cls.custom", "تجربة مخصصة"), ("cls.sensitivity", "تحليل الحساسية"), ("cls.preliminary", "محاكاة أولية"),
    ("cls.estimated", "ارتفاعات تقديرية"), ("cls.pending", "التحقق العلمي قيد الانتظار"),
    ("cls.validated_results", "نتائج بحثية مستوفية للتحقق"), ("nav.reports", "التقارير")])
def test_terminology_table(key, arabic):
    assert arabic in i18n.translate("ar", key)


def test_arabic_terms_for_data_rate_signal_quality_and_synthetic_model():
    assert "معدل نقل البيانات" in i18n.translate("ar", "coverage.layers.rate_bps")
    assert "جودة الإشارة" in i18n.translate("ar", "coverage.layers.sinr_db")
    assert "النموذج الحضري الاصطناعي" in i18n.translate("ar", "study_area.variants.synthetic_urban")


def test_every_scenario_area_and_roadmap_item_has_a_translation():
    scenarios = yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))
    scenarios = scenarios.get("scenarios", scenarios)
    areas = yaml.safe_load((ROOT / "configs" / "study_area.yaml").read_text(encoding="utf-8"))["areas"]
    roadmap = yaml.safe_load((ROOT / "configs" / "roadmap.yaml").read_text(encoding="utf-8"))
    for lang in i18n.LANGUAGES:
        cat = i18n.catalog(lang)
        assert all(f"common.band.{s['id']}" in cat for s in scenarios)
        assert all(f"study_area.names.{a}" in cat for a in areas)
        for stage in roadmap["stages"]:
            assert f"roadmap.stages.{stage['id']}.title" in cat
            assert all(f"roadmap.items.{stage['id']}.i{n}" in cat for n in range(len(stage["items"])))
    # the English item texts are the configuration's own wording: a changed roadmap claim fails here
    for stage in roadmap["stages"]:
        for n, item in enumerate(stage["items"]):
            assert i18n.translate("en", f"roadmap.items.{stage['id']}.i{n}") == " ".join(item["text"].split())


def test_classification_in_arabic_names_no_english_class():
    from bns.analysis import classification as cl

    c = cl.Classification(cl.CUSTOM, cl.ESTIMATED, cl.PENDING,
                          deviations=("preview profile (25 m, 1e+08 rays)",
                                      "GPU backend (numerical limits: docs/validation.md §7)", "tx_power_dbm = 43.0"))
    head, details = i18n.classification_texts(i18n.translator("ar"), c)
    assert head == "تجربة مخصصة"
    for english in ("Custom Experiment", "Estimated Heights", "profile", "backend", "rays"):
        assert english not in details
    assert "tx_power_dbm = 43.0" in details                      # recorded override values stay as recorded
    en_head, en_details = i18n.classification_texts(i18n.translator("en"), c)
    assert en_head == "Custom Experiment" and "preview profile (25 m, 1e+08 rays)" in en_details


def test_arabic_report_is_right_to_left_with_translated_headings(tmp_path):
    from bns.analysis import classification as cl
    from bns.reporting.report import build_html, limitations

    c = cl.Classification(cl.BASELINE, cl.ESTIMATED, cl.PENDING)
    (tmp_path / "manifest.json").write_text(json.dumps({
        "label": c.label, "classification": c.as_dict(), "run_id": "r3", "overrides": {},
        "created_utc": "2026-11-27T01:31:03+00:00", "profile": {"name": "standard", "cell_size_m": 10, "rays_per_site": 1e9},
        "area": {"height_model": {"kind": "synthetic_urban", "name": "synthetic_urban", "seed": 42, "synthetic": 99.4}},
        "radio_parameters": {"tx_power_dbm": {"value": 46.0}}}), encoding="utf-8")
    (tmp_path / "summary.md").write_text("# Simulation Results\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    page = build_html(tmp_path, lang="ar")
    assert "<html lang='ar' dir='rtl'>" in page and "Noto Sans Arabic" in page
    assert "محاكي شبكات بغداد" in page and "القيود العلمية" in page and "27 نوفمبر 2026" in page
    assert "<td>tx_power_dbm</td><td>46.0</td><td>الإعدادات البحثية الأساسية</td>" in page
    assert "البذرة 42" in page and "99.4 %" in page                       # synthetic heights stated, in Arabic
    assert "<div class='source' lang='en' dir='ltr'>" in page            # the English run record stays LTR
    assert all(text in page for text in limitations("ar"))
    english = build_html(tmp_path)
    assert "<html lang='en' dir='ltr'>" in english and "Scientific limitations" in english
    assert not ARABIC.search(english)


def test_limitation_sentences_exist_in_both_languages():
    from bns.reporting.report import LIMITATIONS, limitations

    assert LIMITATIONS == limitations("en") and len(limitations("ar")) == len(LIMITATIONS)
    assert all(ARABIC.search(text) for text in limitations("ar"))

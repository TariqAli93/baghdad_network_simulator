"""Printable run report: Markdown subset, label kept, figures embedded."""

import json

from bns.reporting.report import build_html, markdown_to_html


def test_markdown_subset_converts_headings_tables_lists_and_escapes_html():
    out = markdown_to_html("# Title\n\nSome **bold** `code` <x>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n")
    assert "<h2>Title</h2>" in out and "<b>bold</b>" in out and "<code>code</code>" in out
    assert "&lt;x&gt;" in out
    assert "<th>a</th>" in out and "<td>2</td>" in out and "---" not in out
    assert "<li>one</li><li>two</li>" in out


def test_report_keeps_the_development_label_and_embeds_figures(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "label": "DEVELOPMENT — NOT APPROVED FOR RESEARCH", "run_id": "r1", "mode": "development",
        "profile": {"name": "preview", "cell_size_m": 25, "rays_per_site": 1e8},
        "radio_parameters": {"tx_power_dbm": {"value": 46.0, "status": "candidate"}}}), encoding="utf-8")
    (tmp_path / "summary.md").write_text("| x | y |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    (tmp_path / "fig.png").write_bytes(b"\x89PNG\r\n")
    page = build_html(tmp_path)
    assert page.count("DEVELOPMENT — NOT APPROVED FOR RESEARCH") == 2       # top and bottom
    assert "data:image/png;base64," in page and "candidate" in page
    assert "Scientific limitations" in page and "Shannon rates are theoretical upper bounds" in page

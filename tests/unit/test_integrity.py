"""Checksums of a delivery package and their verification on the student's computer."""

import hashlib

from bns import integrity


def make(tmp_path, files: dict[str, bytes]):
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_checksum_lines_list_every_file_with_its_sha256():
    text = integrity.checksum_text({"b/x.py": b"print(1)\n", "a.txt": b"hello"})
    lines = text.splitlines()
    assert lines == sorted(lines, key=lambda ln: ln.split("  ", 1)[1])          # stable order by path
    assert f"{hashlib.sha256(b'hello').hexdigest()}  a.txt" in lines


def test_files_regenerated_by_setup_are_not_listed():
    assert integrity.listed("src/bns/__init__.py") and integrity.listed("data/raw/osm/a.json")
    assert not integrity.listed("outputs/datasets/area/variant/quality_report.json")
    assert not integrity.listed(integrity.NAME)


def test_verify_reports_missing_and_changed_files(tmp_path):
    files = {"src/a.py": b"a", "configs/c.yaml": b"c: 1\n", "data/raw/x.json": b"{}"}
    make(tmp_path, files)
    (tmp_path / integrity.NAME).write_text(integrity.checksum_text(files), encoding="utf-8")
    ok = integrity.verify(tmp_path)
    assert ok == {"checked": 3, "missing": [], "changed": []}
    (tmp_path / "src" / "a.py").unlink()
    (tmp_path / "configs" / "c.yaml").write_bytes(b"c: 2\n")
    bad = integrity.verify(tmp_path)
    assert bad["missing"] == ["src/a.py"] and bad["changed"] == ["configs/c.yaml"] and bad["checked"] == 3


def test_no_checksum_file_means_not_a_delivery_package(tmp_path):
    assert integrity.verify(tmp_path) is None

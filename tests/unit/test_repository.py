"""Repository settings that protect the hashed raw data."""

import subprocess

import pytest


def test_raw_data_is_never_converted_on_checkout(repo_root):
    if not (repo_root / ".git").exists():
        pytest.skip("not a git checkout (release archive): nothing is checked out")
    # core.autocrlf=true once rewrote an OSM snapshot with CRLF and broke its SHA-256
    out = subprocess.run(["git", "check-attr", "text", "data/raw/osm/any.json"], cwd=repo_root,
                         capture_output=True, text=True, check=True).stdout
    assert out.strip().endswith("text: unset")

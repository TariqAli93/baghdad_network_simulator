"""Repository settings that protect the hashed raw data."""

import subprocess


def test_raw_data_is_never_converted_on_checkout(repo_root):
    # core.autocrlf=true once rewrote an OSM snapshot with CRLF and broke its SHA-256
    out = subprocess.run(["git", "check-attr", "text", "data/raw/osm/any.json"], cwd=repo_root,
                         capture_output=True, text=True, check=True).stdout
    assert out.strip().endswith("text: unset")

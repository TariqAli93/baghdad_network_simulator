"""Interface preferences kept on this computer (the language survives an application restart)."""

from bns.app import preferences


def test_saved_values_are_read_back(tmp_path):
    path = tmp_path / "prefs.json"
    assert preferences.load(path) == {}
    preferences.save(path, lang="en")
    assert preferences.load(path) == {"lang": "en"}
    preferences.save(path, other=1)                      # values are merged, not replaced
    assert preferences.load(path) == {"lang": "en", "other": 1}


def test_a_missing_or_damaged_file_gives_no_preferences(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("{not json", encoding="utf-8")
    assert preferences.load(path) == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert preferences.load(path) == {}


def test_the_location_is_local_state_and_can_be_redirected(tmp_path, monkeypatch):
    monkeypatch.delenv(preferences.ENV, raising=False)
    default = preferences.location(tmp_path)
    assert default == tmp_path / "outputs" / "app_state" / "preferences.json"
    monkeypatch.setenv(preferences.ENV, str(tmp_path / "elsewhere.json"))
    assert preferences.location(tmp_path) == tmp_path / "elsewhere.json"


def test_an_unwritable_location_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    preferences.save(blocker / "prefs.json", lang="en")  # parent is a file: nothing saved, no exception
    assert preferences.load(blocker / "prefs.json") == {}

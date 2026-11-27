import pytest


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path_factory, monkeypatch):
    """App tests never read or change the user's saved interface preferences."""
    from bns.app import preferences

    path = tmp_path_factory.mktemp("prefs") / "preferences.json"
    monkeypatch.setenv(preferences.ENV, str(path))
    return path

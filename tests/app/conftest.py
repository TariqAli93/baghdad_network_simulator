import pytest


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path_factory, monkeypatch):
    """App tests never read or change the user's saved interface preferences."""
    from bns.app import preferences

    path = tmp_path_factory.mktemp("prefs") / "preferences.json"
    monkeypatch.setenv(preferences.ENV, str(path))
    return path


@pytest.fixture(autouse=True)
def isolated_experiments(tmp_path_factory, monkeypatch):
    """App tests never read or change the user's saved experiments."""
    from bns.app import experiments

    path = tmp_path_factory.mktemp("experiments")
    monkeypatch.setenv(experiments.ENV, str(path))
    return path

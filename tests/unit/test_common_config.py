from rh_skills.common import config_value, repo_root


def test_config_precedence_env_over_local_over_global(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".rh-skills.toml").write_text(
        """\
[paths]
repo_root = "/global-root"
"""
    )

    repo = tmp_path / "repo"
    nested = repo / "nested"
    nested.mkdir(parents=True)
    (repo / ".rh-skills.toml").write_text(
        """\
[paths]
repo_root = "/local-root"
"""
    )

    monkeypatch.chdir(nested)
    monkeypatch.setenv("RH_REPO_ROOT", "/env-root")

    assert config_value("RH_REPO_ROOT") == "/env-root"
    assert repo_root().as_posix() == "/env-root"


def test_config_precedence_local_over_global(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".rh-skills.toml").write_text(
        """\
[paths]
repo_root = "/global-root"
"""
    )

    repo = tmp_path / "repo"
    nested = repo / "nested"
    nested.mkdir(parents=True)
    (repo / ".rh-skills.toml").write_text(
        """\
[paths]
repo_root = "/local-root"
"""
    )

    monkeypatch.chdir(nested)
    monkeypatch.delenv("RH_REPO_ROOT", raising=False)

    assert config_value("RH_REPO_ROOT") == "/local-root"
    assert repo_root().as_posix() == "/local-root"


def test_config_uses_global_when_no_env_or_local(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".rh-skills.toml").write_text(
        """\
[paths]
repo_root = "/global-root"
"""
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.delenv("RH_REPO_ROOT", raising=False)

    assert config_value("RH_REPO_ROOT") == "/global-root"
    assert repo_root().as_posix() == "/global-root"

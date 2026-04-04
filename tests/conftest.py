"""Shared pytest fixtures for hi CLI tests."""

import os
from pathlib import Path

import pytest
from ruamel.yaml import YAML


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal repo structure with tracking.yaml."""
    topics = tmp_path / "topics"
    topics.mkdir()
    sources = tmp_path / "sources"
    sources.mkdir()
    plans = tmp_path / "plans"
    plans.mkdir()
    tracking = tmp_path / "tracking.yaml"
    y = YAML()
    y.default_flow_style = False
    y.dump({"schema_version": "1.0", "sources": [], "topics": [], "events": []}, tracking)

    env_overrides = {
        "HI_REPO_ROOT": str(tmp_path),
        "HI_TOPICS_ROOT": str(topics),
        "HI_TRACKING_FILE": str(tracking),
        "HI_SOURCES_ROOT": str(sources),
    }
    old = {k: os.environ.get(k) for k in env_overrides}
    for k, v in env_overrides.items():
        os.environ[k] = v
    yield tmp_path
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def tmp_topic(tmp_repo):
    """Create a test topic inside tmp_repo."""
    from click.testing import CliRunner
    from hi.commands.init import init
    runner = CliRunner()
    result = runner.invoke(init, ["test-topic", "--title", "Test Topic"])
    assert result.exit_code == 0, result.output
    return tmp_repo


def make_tracking(tmp_repo, topics=None, sources=None):
    """Helper to write tracking.yaml with given data."""
    y = YAML()
    y.default_flow_style = False
    data = {
        "schema_version": "1.0",
        "sources": sources or [],
        "topics": topics or [],
        "events": [],
    }
    tracking = tmp_repo / "tracking.yaml"
    y.dump(data, tracking)
    return data


def load_tracking(tmp_repo) -> dict:
    """Helper to read tracking.yaml from tmp_repo."""
    y = YAML()
    with open(tmp_repo / "tracking.yaml") as f:
        return y.load(f)

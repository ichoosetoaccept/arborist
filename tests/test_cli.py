"""Test the CLI interface."""

import logging
from pathlib import Path
from typing import Generator

import pytest
from git.repo.base import Repo
from typer.testing import CliRunner

from arborist.cli import app

# Configure logging to show debug messages in test output
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Add formatter to ch
ch.setFormatter(formatter)

# Add ch to logger
logger.addHandler(ch)

logger.debug("Initializing test module")


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture for CLI runner."""
    return CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture
def cli_app() -> Generator:
    """Fixture for CLI app."""
    yield app


def test_clean_command(cli_runner: CliRunner, cli_app, temp_repo: Repo) -> None:
    """Test clean command."""
    # Create test branches
    temp_repo.git.branch("feature/merged")
    temp_repo.git.branch("feature/unmerged")

    # Make a change on main
    main_file = Path(temp_repo.working_dir) / "main.txt"
    main_file.write_text("main branch change")
    temp_repo.index.add([str(main_file)])
    temp_repo.index.commit("Change on main")

    # Make a change on feature/merged and merge it into main
    temp_repo.git.checkout("feature/merged")
    merged_file = Path(temp_repo.working_dir) / "merged.txt"
    merged_file.write_text("merged branch change")
    temp_repo.index.add([str(merged_file)])
    temp_repo.index.commit("Change on feature/merged")
    temp_repo.git.checkout("main")
    temp_repo.git.merge("feature/merged")

    # Make a change on feature/unmerged
    temp_repo.git.checkout("feature/unmerged")
    unmerged_file = Path(temp_repo.working_dir) / "unmerged.txt"
    unmerged_file.write_text("unmerged branch change")
    temp_repo.index.add([str(unmerged_file)])
    temp_repo.index.commit("Change on feature/unmerged")
    temp_repo.git.checkout("main")

    logger.debug(f"Invoking clean command with path: {temp_repo.working_dir}")
    result = cli_runner.invoke(cli_app, ["clean", "--no-interactive", "--path", str(temp_repo.working_dir)])
    logger.debug(f"Command output: {result.output}")
    logger.debug(f"Command exit code: {result.exit_code}")
    assert result.exit_code == 0
    assert "feature/merged" in result.output
    assert "feature/unmerged" not in result.output


def test_list_command(cli_runner: CliRunner, cli_app, temp_repo: Repo) -> None:
    """Test list command."""
    # Create test branches
    temp_repo.git.branch("feature/test")

    logger.debug(f"Invoking list command with path: {temp_repo.working_dir}")
    result = cli_runner.invoke(cli_app, ["list", "--path", str(temp_repo.working_dir)])
    logger.debug(f"Command output: {result.output}")
    logger.debug(f"Command exit code: {result.exit_code}")
    assert result.exit_code == 0
    assert "main" in result.output
    assert "feature/test" in result.output


if __name__ == "__main__":
    pytest.main(["-v", __file__])

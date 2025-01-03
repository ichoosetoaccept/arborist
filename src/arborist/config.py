"""Configuration handling for arborist."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from arborist.errors import ConfigError, ErrorCode


class BranchConfig(BaseModel):
    """Branch-specific configuration."""

    protected_patterns: List[str] = Field(
        default=["main", "master"],
        description="Branch name patterns that should be protected from deletion",
    )
    name_pattern: str = Field(
        default=r"^[a-zA-Z0-9][a-zA-Z0-9/_-]*[a-zA-Z0-9]$",
        description="Regex pattern for valid branch names",
    )
    invalid_chars: List[str] = Field(
        default=["~", "^", ":", "\\", " ", "*", "?", "[", "]"],
        description="Characters that are not allowed in branch names",
    )

    @field_validator("name_pattern")
    @classmethod
    def validate_name_pattern(cls, v: str) -> str:
        """Validate branch name pattern.

        Parameters
        ----------
        v : str
            Pattern to validate

        Returns
        -------
        str
            Validated pattern

        Raises
        ------
        ValueError
            If pattern is not a valid regex
        """
        try:
            re.compile(v)
            return v
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e


class GitConfig(BaseModel):
    """Git-specific configuration."""

    reflog_expiry: str = Field(
        default="90.days",
        description="How long to keep reflog entries",
    )
    gc_auto: bool = Field(
        default=True,
        description="Whether to run git gc automatically",
    )
    fetch_prune: bool = Field(
        default=True,
        description="Whether to prune when fetching",
    )


class ArboristConfig(BaseSettings):
    """Configuration for arborist."""

    model_config = SettingsConfigDict(
        env_prefix="ARBORIST_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Branch configuration
    branch: BranchConfig = Field(
        default_factory=BranchConfig,
        description="Branch-specific configuration",
    )

    # Git configuration
    git: GitConfig = Field(
        default_factory=GitConfig,
        description="Git-specific configuration",
    )

    # General settings
    dry_run_by_default: bool = Field(
        default=False,
        description="Whether to run in dry-run mode by default",
    )
    interactive: bool = Field(
        default=True,
        description="Whether to run in interactive mode by default",
    )
    log_level: str = Field(
        default="INFO",
        description="Default logging level",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.

        Parameters
        ----------
        v : str
            Log level to validate

        Returns
        -------
        str
            Validated log level

        Raises
        ------
        ValueError
            If log level is invalid
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {', '.join(valid_levels)}")
        return v.upper()

    def save_config(self, path: Optional[Path] = None) -> None:
        """Save configuration to file.

        Parameters
        ----------
        path : Optional[Path]
            Path to save configuration to. If None, uses default location.

        Raises
        ------
        ConfigError
            If configuration cannot be saved
        """
        if path is None:
            path = Path.home() / ".arboristrc"

        try:
            path.write_text(self.model_dump_json(indent=2))
        except Exception as e:
            raise ConfigError(
                message="Failed to save configuration",
                code=ErrorCode.CONFIG_PERMISSION,
                details=str(path),
                cause=e,
            ) from e

    def _update_from_file(self, file_config: "ArboristConfig") -> None:
        """Update config from file if not set by environment.

        Parameters
        ----------
        file_config : ArboristConfig
            Configuration loaded from file
        """
        env_settings = self.get_env_settings()
        if not env_settings.get("ARBORIST_BRANCH__PROTECTED_PATTERNS"):
            self.branch.protected_patterns = file_config.branch.protected_patterns
        if not env_settings.get("ARBORIST_BRANCH__NAME_PATTERN"):
            self.branch.name_pattern = file_config.branch.name_pattern
        if not env_settings.get("ARBORIST_BRANCH__INVALID_CHARS"):
            self.branch.invalid_chars = file_config.branch.invalid_chars
        if not env_settings.get("ARBORIST_GIT__REFLOG_EXPIRY"):
            self.git.reflog_expiry = file_config.git.reflog_expiry
        if not env_settings.get("ARBORIST_GIT__GC_AUTO"):
            self.git.gc_auto = file_config.git.gc_auto
        if not env_settings.get("ARBORIST_GIT__FETCH_PRUNE"):
            self.git.fetch_prune = file_config.git.fetch_prune
        if not env_settings.get("ARBORIST_DRY_RUN_BY_DEFAULT"):
            self.dry_run_by_default = file_config.dry_run_by_default
        if not env_settings.get("ARBORIST_INTERACTIVE"):
            self.interactive = file_config.interactive
        if not env_settings.get("ARBORIST_LOG_LEVEL"):
            self.log_level = file_config.log_level

    @classmethod
    def load_config(cls, path: Optional[str] = None) -> "ArboristConfig":
        """Load configuration from file and environment.

        Parameters
        ----------
        path : Optional[str]
            Path to configuration file. If None, uses default location.

        Returns
        -------
        ArboristConfig
            Loaded configuration

        Raises
        ------
        ConfigError
            If configuration cannot be loaded
        """
        # Create base config from environment variables
        config = cls()

        # Load from file if it exists
        if path is None:
            path = str(Path.home() / ".arboristrc")

        try:
            config_path = Path(path)
            if config_path.exists():
                file_config = cls.model_validate_json(config_path.read_text())
                config._update_from_file(file_config)
            return config
        except Exception as e:
            raise ConfigError(
                message="Failed to load configuration",
                code=ErrorCode.CONFIG_INVALID,
                details=str(path),
                cause=e,
            ) from e

    def get_env_settings(self) -> Dict[str, Any]:
        """Get all environment-based settings.

        Returns
        -------
        Dict[str, Any]
            Dictionary of environment-based settings
        """
        return {key: value for key, value in os.environ.items() if key.startswith("ARBORIST_")}

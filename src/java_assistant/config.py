from dataclasses import dataclass
import os
from pathlib import Path


def _xdg_path(variable: str, fallback: Path) -> Path:
    return Path(os.environ.get(variable, fallback)).expanduser().resolve() / "java-assistente"


@dataclass(frozen=True, slots=True)
class AppConfig:
    project_root: Path
    data_dir: Path
    config_dir: Path
    state_dir: Path

    @classmethod
    def load(cls, cwd: Path) -> "AppConfig":
        home = Path.home()
        return cls(
            project_root=cwd.expanduser().resolve(),
            data_dir=_xdg_path("XDG_DATA_HOME", home / ".local" / "share"),
            config_dir=_xdg_path("XDG_CONFIG_HOME", home / ".config"),
            state_dir=_xdg_path("XDG_STATE_HOME", home / ".local" / "state"),
        )


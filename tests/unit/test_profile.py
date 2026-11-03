import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.profile import (
    DEFAULT_COMMANDS,
    DEFAULT_SECTIONS,
    Profile,
    ProfileError,
    default_profile,
    ensure_profile,
    load_profile,
    merge_profile,
    verify_paths,
)


def base_profile() -> dict:
    return {
        "schema_version": 1,
        "language": {"id": "java8", "source_extension": ".java"},
        "toolchain": {
            "compiler": "tools/native/bin/javac",
            "runtime": "tools/native/bin/java",
            "inspector": "tools/native/bin/javap",
        },
        "libraries": [],
        "limits": {
            "compile_timeout_s": 30,
            "run_timeout_s": 15,
            "inspect_timeout_s": 10,
            "repair_attempts": 2,
            "max_files": 40,
            "context_tokens": 4096,
            "output_tokens": 640,
        },
        "context": {"chars_per_token": 3.5, "sections": dict(DEFAULT_SECTIONS)},
        "commands": {key: list(value) for key, value in DEFAULT_COMMANDS.items()},
    }


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class ProfileTests(unittest.TestCase):
    def _config(self, root: Path) -> AppConfig:
        return AppConfig(root / "projeto", root / "dados", root / "config", root / "estado")

    def _load(self, root: Path, config: AppConfig) -> Profile:
        return load_profile(
            config, app_home=root, available_adapters=("java8",)
        )

    def test_global_profile_merges_project_override_field_by_field(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            global_data = base_profile()
            global_data["limits"]["repair_attempts"] = 1
            write(config.config_dir / "perfil.json", global_data)
            write(
                config.project_root / ".assistente" / "perfil.json",
                {
                    "limits": {"repair_attempts": 3},
                    "commands": {"pdf": ["/enunciado"]},
                },
            )

            profile = self._load(root, config)

            self.assertEqual(3, profile.limits.repair_attempts)
            self.assertEqual(("/enunciado",), profile.commands["pdf"])
            self.assertEqual(("/sair", "sair"), profile.commands["exit"])
            self.assertEqual("project", profile.origin)
            self.assertIsNotNone(profile.project_path)

    def test_lists_replace_instead_of_concatenating(self) -> None:
        merged = merge_profile(
            {"libraries": ["global.jar"], "commands": {"pdf": ["/pdf"]}},
            {"libraries": ["projeto.jar"], "commands": {"pdf": ["/enunciado"]}},
        )

        self.assertEqual(["projeto.jar"], merged["libraries"])
        self.assertEqual(["/enunciado"], merged["commands"]["pdf"])

    def test_unknown_key_names_the_accepted_ones(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["limite"] = {}
            write(config.config_dir / "perfil.json", data)

            with self.assertRaises(ProfileError) as caught:
                self._load(root, config)

            self.assertIn("limite", str(caught.exception))
            self.assertIn("limits", str(caught.exception))

    def test_output_tokens_must_be_smaller_than_context(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["limits"]["output_tokens"] = 4096
            write(config.config_dir / "perfil.json", data)

            with self.assertRaises(ProfileError) as caught:
                self._load(root, config)

            self.assertIn("output_tokens", str(caught.exception))

    def test_exit_command_is_mandatory(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            del data["commands"]["exit"]
            write(config.config_dir / "perfil.json", data)

            with self.assertRaises(ProfileError) as caught:
                self._load(root, config)

            self.assertIn("exit", str(caught.exception))

    def test_aliases_cannot_collide_across_commands(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["commands"]["undo"] = ["/pdf"]
            write(config.config_dir / "perfil.json", data)

            with self.assertRaises(ProfileError) as caught:
                self._load(root, config)

            self.assertIn("/pdf", str(caught.exception))

    def test_unknown_language_lists_available_adapters(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["language"]["id"] = "python3"
            write(config.config_dir / "perfil.json", data)

            with self.assertRaises(ProfileError) as caught:
                self._load(root, config)

            message = str(caught.exception)
            self.assertIn("python3", message)
            self.assertIn("java8", message)

    def test_rejects_out_of_range_numbers_and_unknown_sections(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["limits"]["repair_attempts"] = 9
            write(config.config_dir / "perfil.json", data)
            with self.assertRaises(ProfileError):
                self._load(root, config)

            data = base_profile()
            data["context"]["sections"]["inventada"] = 10
            write(config.config_dir / "perfil.json", data)
            with self.assertRaises(ProfileError):
                self._load(root, config)

    def test_rejects_nan_ratio_and_float_schema_version(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["context"]["chars_per_token"] = float("nan")
            write(config.config_dir / "perfil.json", data)
            with self.assertRaises(ProfileError):
                self._load(root, config)

            data = base_profile()
            data["schema_version"] = 1.0
            write(config.config_dir / "perfil.json", data)
            with self.assertRaises(ProfileError):
                self._load(root, config)

    def test_trims_paths_aliases_and_extension(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            data = base_profile()
            data["toolchain"]["compiler"] = " tools/native/bin/javac "
            data["language"]["source_extension"] = " .java "
            data["commands"]["pdf"] = [" /pdf "]
            write(config.config_dir / "perfil.json", data)

            profile = self._load(root, config)

            self.assertEqual(root / "tools/native/bin/javac", profile.toolchain["compiler"])
            self.assertEqual(".java", profile.source_extension)
            self.assertEqual(("/pdf",), profile.commands["pdf"])

    def test_ensure_profile_preserves_user_edit_and_verify_paths_reports_missing(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            template = root / "perfil-padrao.json"
            write(template, base_profile())

            target = ensure_profile(config, template)
            target.write_text('{"schema_version": 1}', encoding="utf-8")
            ensure_profile(config, template)

            self.assertEqual('{"schema_version": 1}', target.read_text(encoding="utf-8"))

            profile = default_profile(root)
            with self.assertRaises(ProfileError) as caught:
                verify_paths(profile)
            self.assertIn(str(profile.toolchain["compiler"]), str(caught.exception))

    def test_default_profile_matches_the_packaged_contract(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            profile = default_profile(root)

            self.assertEqual("java8", profile.language_id)
            self.assertEqual(".java", profile.source_extension)
            self.assertEqual(4096, profile.limits.context_tokens)
            self.assertEqual(640, profile.limits.output_tokens)
            self.assertEqual(3.5, profile.context.chars_per_token)
            self.assertEqual(dict(DEFAULT_SECTIONS), dict(profile.context.sections))
            self.assertEqual(("/sair", "sair"), profile.commands["exit"])
            self.assertEqual(root / "tools/native/bin/javac", profile.toolchain["compiler"])


if __name__ == "__main__":
    unittest.main()

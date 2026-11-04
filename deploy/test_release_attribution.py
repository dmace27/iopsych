"""Read-only Compose attribution checks; no daemon, builds or containers."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


COMPOSE = Path(__file__).with_name("compose.yaml").resolve()


class ReleaseAttributionTests(unittest.TestCase):
    def render(self, values):
        environment = {"PATH": os.environ["PATH"], **values}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "docker", "compose", "--env-file", "/dev/null",
                    "-f", str(COMPOSE), "--profile", "tools",
                    "config", "--format", "json",
                ],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        return json.loads(result.stdout)

    def assert_attribution(self, values, expected):
        model = self.render(values)
        for name, image in (("api", "api"), ("migrate", "api"), ("web", "web")):
            with self.subTest(service=name):
                service = model["services"][name]
                self.assertEqual(service["image"], f"iopsych-{image}:{expected}")
                self.assertEqual(service["build"]["args"]["REVISION"], expected)
                self.assertEqual(service["environment"]["IOPSYCH_RELEASE_ID"], expected)
        self.assertNotIn("IOPSYCH_RELEASE_ID", model["services"]["db"]["environment"])

    def test_supplied_source_revision(self):
        revision = "0123456789abcdef0123456789abcdef01234567"
        self.assert_attribution({"REVISION": revision}, revision)

    def test_supplied_release_identifier(self):
        self.assert_attribution({"REVISION": "synthetic-2026.11_04"}, "synthetic-2026.11_04")

    def test_missing_revision_is_unknown(self):
        self.assert_attribution({}, "unknown")

    def test_empty_revision_is_unknown(self):
        self.assert_attribution({"REVISION": ""}, "unknown")

    def test_host_runtime_id_cannot_diverge_from_revision(self):
        self.assert_attribution(
            {"REVISION": "synthetic-source", "IOPSYCH_RELEASE_ID": "unrelated-host"},
            "synthetic-source",
        )

    def test_host_runtime_id_cannot_invent_missing_revision(self):
        self.assert_attribution({"IOPSYCH_RELEASE_ID": "unrelated-host"}, "unknown")


if __name__ == "__main__":
    unittest.main()

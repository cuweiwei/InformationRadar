import re
import unittest
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "container.yml"
DOCKERFILE = Path(__file__).parents[1] / "Dockerfile"


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    def test_all_actions_are_pinned_to_full_commit_shas(self):
        actions = re.findall(r"^\s*- uses: (\S+)", self.workflow, re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^[^@\s]+@[0-9a-f]{40}$")

    def test_image_release_gate_is_immutable_linux_amd64(self):
        self.assertIn("platforms: linux/amd64", self.workflow)
        self.assertIn("pull: true", self.workflow)
        self.assertIn("provenance: mode=max", self.workflow)
        self.assertIn("sbom: true", self.workflow)
        self.assertIn("image-ref: ghcr.io/${{ github.repository_owner }}/information-radar@${{ steps.build.outputs.digest }}", self.workflow)
        self.assertIn("scanners: vuln", self.workflow)
        self.assertIn("severity: HIGH,CRITICAL", self.workflow)
        self.assertIn("exit-code: '1'", self.workflow)
        self.assertIn("ignore-unfixed: true", self.workflow)

    def test_runtime_base_and_fixable_tooling_are_pinned(self):
        self.assertRegex(self.dockerfile, r"FROM python:3\.11-slim@sha256:[0-9a-f]{64}")
        self.assertIn("apt-get upgrade -y", self.dockerfile)
        self.assertIn("pip uninstall -y setuptools wheel", self.dockerfile)

    def test_release_artifact_is_emitted_only_after_cve_gate(self):
        scan = self.workflow.index("name: Scan published image for HIGH and CRITICAL CVEs")
        manifest = self.workflow.index("name: Generate AI Home Platform release manifest")
        upload = self.workflow.index("name: Upload AI Home Platform release manifest")
        self.assertLess(scan, manifest)
        self.assertLess(manifest, upload)
        self.assertIn("name: aihome-release-${{ github.sha }}", self.workflow)


if __name__ == "__main__":
    unittest.main()

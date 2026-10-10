import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dependencies
import prepare_release


DOCKERFILE = """# syntax=docker/dockerfile:1.7
ARG CADDY_VERSION=2.11.4
ARG CADDY_BUILDER_IMAGE=caddy:2.11.4-builder-alpine@sha256:old
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.4-alpine@sha256:old
FROM --platform=${BUILDPLATFORM} ${CADDY_BUILDER_IMAGE} AS builder
ARG CADDY_VERSION
ARG BUNNY_IP_VERSION=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ARG BUNNY_DNS_VERSION=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
RUN xcaddy build "v${CADDY_VERSION}"
FROM ${CADDY_RUNTIME_IMAGE}
"""
FRONTEND = "docker/dockerfile:1@sha256:" + "f" * 64


class DependenciesTests(unittest.TestCase):
    def setUp(self):
        self.pins = dependencies.read_pins(DOCKERFILE)

    def test_version_images_and_modules_change_together(self):
        pins = dict(self.pins, CADDY_VERSION="2.12.0",
                    CADDY_BUILDER_IMAGE="caddy:2.12.0-builder-alpine@sha256:" + "c" * 64,
                    CADDY_RUNTIME_IMAGE="caddy:2.12.0-alpine@sha256:" + "d" * 64,
                    BUNNY_IP_VERSION="e" * 40)
        updated = dependencies.update_content(DOCKERFILE, pins, FRONTEND)
        self.assertEqual(dependencies.read_pins(updated), pins)
        self.assertIn("ARG CADDY_VERSION\n", updated)
        self.assertIn('RUN xcaddy build "v${CADDY_VERSION}"', updated)
        self.assertTrue(updated.startswith(f"# syntax={FRONTEND}\n"))
        self.assertNotIn("2.11.4", updated)

    def test_duplicate_or_missing_pins_are_rejected(self):
        for content in (DOCKERFILE + "ARG CADDY_VERSION=2.12.0\n",
                        DOCKERFILE.replace("ARG BUNNY_IP_VERSION=", "ARG OTHER=")):
            with self.subTest(content=content), self.assertRaises(ValueError):
                dependencies.read_pins(content)

    def test_missing_frontend_is_rejected(self):
        with self.assertRaises(ValueError):
            dependencies.update_content(DOCKERFILE.split("\n", 1)[1], self.pins, FRONTEND)

    def test_image_digest_is_the_multiplatform_index(self):
        manifest = {"digest": "sha256:" + "c" * 64, "manifests": [
            {"digest": "sha256:" + "d" * 64, "platform": {"os": "linux", "architecture": "amd64"}},
            {"platform": {"os": "linux", "architecture": "arm64"}},
        ]}
        with patch.object(dependencies, "command", return_value=json.dumps(manifest)):
            self.assertEqual(dependencies.image_pin("caddy:2.12.0-alpine"),
                             "caddy:2.12.0-alpine@sha256:" + "c" * 64)

    def test_incomplete_platforms_or_bad_digest_abort(self):
        for manifest in ({"digest": "sha256:" + "c" * 64, "manifests": []},
                         {"digest": "bad", "manifests": []}):
            with self.subTest(manifest=manifest), patch.object(dependencies, "command", return_value=json.dumps(manifest)):
                with self.assertRaises(ValueError):
                    dependencies.image_pin("caddy:2.12.0-alpine")

    def test_only_stable_releases_are_accepted(self):
        for release in ({"tag_name": "v2.12.0-rc1", "draft": False, "prerelease": True},
                        {"tag_name": "v2.12.0", "draft": True, "prerelease": False}):
            with self.subTest(release=release), patch.object(dependencies, "github_json", return_value=release):
                with self.assertRaises(ValueError):
                    dependencies.resolve_pins(self.pins)

    def test_upstream_release_cannot_downgrade_a_pin(self):
        with patch.object(dependencies, "github_json", return_value={
            "tag_name": "v2.10.9", "draft": False, "prerelease": False,
        }), patch.object(dependencies, "image_pin", side_effect=lambda image: image + "@sha256:" + "c" * 64), \
                patch.object(dependencies, "module_commit", return_value="e" * 40):
            updated = dependencies.resolve_pins(self.pins)
        self.assertEqual(updated["CADDY_VERSION"], "2.11.4")
        self.assertIn(":2.11.4-", updated["CADDY_RUNTIME_IMAGE"])

    def test_module_sha_is_validated(self):
        with patch.object(dependencies, "github_json", return_value=[{"sha": "main"}]):
            with self.assertRaises(ValueError):
                dependencies.module_commit("owner/repository")

    def test_resolution_failure_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Dockerfile"
            path.write_text(DOCKERFILE)
            with patch.object(dependencies, "resolve_pins", return_value=self.pins), \
                    patch.object(dependencies, "image_pin", side_effect=RuntimeError("registry unavailable")):
                with self.assertRaises(RuntimeError):
                    dependencies.update(path)
            self.assertEqual(path.read_text(), DOCKERFILE)

    def test_dry_run_does_not_write_and_second_update_is_noop(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(dependencies, "resolve_pins", return_value=self.pins), \
                patch.object(dependencies, "image_pin", return_value=FRONTEND), \
                patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / "Dockerfile"
            path.write_text(DOCKERFILE)
            self.assertTrue(dependencies.update(path, dry_run=True))
            self.assertEqual(path.read_text(), DOCKERFILE)
            self.assertTrue(dependencies.update(path))
            self.assertFalse(dependencies.update(path))


class ReleaseTests(unittest.TestCase):
    def test_first_release_and_new_caddy_version_start_at_one(self):
        self.assertEqual(prepare_release.select_tag("2.12.0", ["v2.11.4-5"], []), "v2.12.0-1")

    def test_revision_sorting_is_numeric_and_reserved_tags_are_counted(self):
        self.assertEqual(prepare_release.select_tag("2.11.4", [
            "v2.11.4-2", "v2.11.4-10", "v2.11.4-9", "v2.11.4-rc1", "v2.11.40-99",
        ], []), "v2.11.4-11")

    def test_retry_reuses_tag_for_same_commit(self):
        self.assertEqual(prepare_release.select_tag("2.11.4", ["v2.11.4-2"], ["v2.11.4-2"]), "v2.11.4-2")

    def test_manual_tag_must_match_caddy_and_commit(self):
        for requested, head_tags in (("v2.11.5-1", ["v2.11.5-1"]),
                                     ("v2.11.4-2", []), ("v2.11.4-0", ["v2.11.4-0"])):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                prepare_release.select_tag("2.11.4", head_tags, head_tags, requested)

    def run_prepare(self, releases, tags=None, dry_run=False):
        tags = ["v2.11.4-1"] if tags is None else tags

        def command(*args):
            if args[:2] == ("git", "status"):
                return ""
            if args[:2] == ("git", "tag"):
                return "\n".join(tags)
            if args[:2] == ("gh", "api"):
                return json.dumps([releases])
            self.fail(f"Unexpected command: {args}")

        with patch.object(prepare_release, "command", side_effect=command), \
                patch.object(Path, "read_text", return_value=DOCKERFILE), \
                patch.object(prepare_release.subprocess, "run") as mutation, \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_REF": "refs/heads/main"}, clear=True), \
                contextlib.redirect_stdout(io.StringIO()):
            result = prepare_release.prepare(dry_run)
            return result, mutation.call_args_list

    def test_published_release_never_pushes_tags_or_rebuilds(self):
        result, mutations = self.run_prepare([{"tag_name": "v2.11.4-1", "draft": False}])
        self.assertFalse(result)
        self.assertEqual(mutations, [])

    def test_draft_release_is_resumed_without_creating_another_release(self):
        result, mutations = self.run_prepare([{"tag_name": "v2.11.4-1", "draft": True}])
        self.assertTrue(result)
        self.assertEqual([call.args[0][:2] for call in mutations], [["git", "push"]])

    def test_new_release_reserves_tag_and_creates_only_a_draft(self):
        result, mutations = self.run_prepare([], tags=[])
        self.assertTrue(result)
        commands = [call.args[0] for call in mutations]
        self.assertEqual(commands[0], ["git", "tag", "v2.11.4-1", "HEAD"])
        self.assertEqual(commands[1], ["git", "push", "origin", "refs/tags/v2.11.4-1"])
        self.assertIn("--draft", commands[2])
        self.assertIn("--verify-tag", commands[2])
        self.assertIn("--notes-file", commands[2])

    def test_dry_run_has_no_remote_mutations(self):
        result, mutations = self.run_prepare([], tags=[], dry_run=True)
        self.assertTrue(result)
        self.assertEqual(mutations, [])

    def test_uncommitted_pins_cannot_be_tagged_as_a_release(self):
        with patch.object(prepare_release, "command", return_value=" M Dockerfile"), \
                patch.object(prepare_release.subprocess, "run") as mutation:
            with self.assertRaises(ValueError):
                prepare_release.prepare()
            mutation.assert_not_called()


class ImageVersionTests(unittest.TestCase):
    def test_version_check_rejects_prefix_matches_and_adapts_to_pin_changes(self):
        # Fake only Docker, exercising the real shell script's version comparison.
        script = Path(__file__).resolve().parents[1] / "scripts/test-image.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            copied = root / "scripts/test-image.sh"
            copied.write_text(script.read_text())
            (root / "Dockerfile").write_text("ARG CADDY_VERSION=2.12.0\n")
            docker = root / "docker"
            docker.write_text('''#!/bin/sh
case "$*" in
  *"caddy version") printf '%s\n' "$FAKE_VERSION" ;;
  *"caddy list-modules") printf '%s\n' http.ip_sources.bunny dns.providers.bunny ;;
esac
''')
            docker.chmod(0o755)
            for version, success in (("v2.12.0 h1:hash", True), ("v2.12.00 h1:hash", False),
                                     ("v2.12.0-rc1", False), ("v2.11.4", False)):
                with self.subTest(version=version):
                    env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", FAKE_VERSION=version)
                    result = subprocess.run(["sh", str(copied)], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, success, result.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Reserve a new image release, or resume an interrupted draft release."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from dependencies import command, read_pins, write_outputs


def select_tag(version, tags, head_tags, requested_tag=None):
    pattern = re.compile(rf"v{re.escape(version)}-([1-9][0-9]*)$")
    if requested_tag:
        if not pattern.fullmatch(requested_tag) or requested_tag not in head_tags:
            raise ValueError("Release tag must match the pinned Caddy version and checked-out commit")
        return requested_tag
    candidates = [tag for tag in head_tags if pattern.fullmatch(tag)]
    if candidates:
        return max(candidates, key=lambda tag: int(pattern.fullmatch(tag)[1]))
    revisions = [int(pattern.fullmatch(tag)[1]) for tag in tags if pattern.fullmatch(tag)]
    return f"v{version}-{max(revisions, default=0) + 1}"


def prepare(dry_run=False):
    if not dry_run and command("git", "status", "--porcelain"):
        raise ValueError("Commit local changes before preparing a release")
    pins = read_pins(Path("Dockerfile").read_text())
    tags = command("git", "tag", "--list").splitlines()
    head_tags = command("git", "tag", "--points-at", "HEAD").splitlines()
    ref = os.environ.get("GITHUB_REF", "")
    requested = ref.removeprefix("refs/tags/") if ref.startswith("refs/tags/") else None
    tag = select_tag(pins["CADDY_VERSION"], tags, head_tags, requested)
    repo = os.environ.get("GITHUB_REPOSITORY") or command("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    pages = json.loads(command("gh", "api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
    releases = {release["tag_name"]: release for page in pages for release in page}
    release = releases.get(tag)
    publish = release is None or release["draft"]
    if publish and not dry_run:
        if tag not in tags:
            subprocess.run(["git", "tag", tag, "HEAD"], check=True)
        # Never force-update a tag. Reserving it before building makes retries deterministic.
        subprocess.run(["git", "push", "origin", f"refs/tags/{tag}"], check=True)
        if release is None:
            notes = (
                f"Caddy {pins['CADDY_VERSION']} with Bunny trusted-proxy and DNS modules.\n\n"
                f"Image: `ghcr.io/{repo.lower()}:{tag[1:]}`\n\n"
                "Pinned build inputs:\n\n"
                + "".join(f"- {name}: `{value}`\n" for name, value in pins.items())
                + "\nAutomatically published after image validation, multi-platform build, and provenance attestation.\n"
            )
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md") as body:
                body.write(notes)
                body.flush()
                subprocess.run([
                    "gh", "release", "create", tag, "--repo", repo,
                    "--draft", "--verify-tag", "--title", tag, "--notes-file", body.name,
                ], check=True)
    write_outputs(tag=tag, version=tag[1:], publish=str(publish).lower())
    return publish


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    prepare(parser.parse_args().dry_run)

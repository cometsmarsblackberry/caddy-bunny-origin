#!/usr/bin/env python3
"""Resolve and pin upstream dependencies without changing a published release."""

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import subprocess


PIN_NAMES = (
    "CADDY_VERSION",
    "CADDY_BUILDER_IMAGE",
    "CADDY_RUNTIME_IMAGE",
    "BUNNY_IP_VERSION",
    "BUNNY_DNS_VERSION",
)


def command(*args):
    return subprocess.check_output(args, text=True, timeout=120).strip()


def read_pins(content):
    pins = {}
    for name in PIN_NAMES:
        values = re.findall(rf"^ARG {name}=(\S+)$", content, re.MULTILINE)
        if len(values) != 1:
            raise ValueError(f"Expected exactly one ARG {name}=... in Dockerfile")
        pins[name] = values[0]
    if not re.fullmatch(r"\d+\.\d+\.\d+", pins["CADDY_VERSION"]):
        raise ValueError("CADDY_VERSION must be a stable semantic version")
    return pins


def github_json(endpoint):
    return json.loads(command("gh", "api", endpoint))


def image_pin(image):
    manifest = json.loads(command(
        "docker", "buildx", "imagetools", "inspect", image,
        "--format", "{{json .Manifest}}",
    ))
    digest = manifest["digest"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError(f"Invalid image digest for {image}")
    platforms = {
        (entry.get("platform", {}).get("os"), entry.get("platform", {}).get("architecture"))
        for entry in manifest.get("manifests", [])
    }
    if not {("linux", "amd64"), ("linux", "arm64")} <= platforms:
        raise ValueError(f"{image} is not available for both amd64 and arm64 yet")
    return f"{image}@{digest}"


def module_commit(repository):
    sha = github_json(f"repos/{repository}/commits?per_page=1")[0]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"Invalid commit SHA for {repository}")
    return sha


def resolve_pins(current):
    release = github_json("repos/caddyserver/caddy/releases/latest")
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", release["tag_name"])
    if not match or release["draft"] or release["prerelease"]:
        raise ValueError("Expected a stable Caddy release")
    version = match[1]
    if tuple(map(int, version.split("."))) < tuple(map(int, current["CADDY_VERSION"].split("."))):
        # The registry/release API may lag a version already pinned by a maintainer.
        version = current["CADDY_VERSION"]
    return {
        "CADDY_VERSION": version,
        "CADDY_BUILDER_IMAGE": image_pin(f"caddy:{version}-builder-alpine"),
        "CADDY_RUNTIME_IMAGE": image_pin(f"caddy:{version}-alpine"),
        "BUNNY_IP_VERSION": module_commit("digilolnet/caddy-bunny-ip"),
        "BUNNY_DNS_VERSION": module_commit("caddy-dns/bunny"),
    }


def update_content(content, pins, frontend):
    read_pins(content)
    for name in PIN_NAMES:
        content = re.sub(rf"^ARG {name}=\S+$", f"ARG {name}={pins[name]}", content, flags=re.MULTILINE)
    content, count = re.subn(r"^# syntax=docker/dockerfile:\S+$", f"# syntax={frontend}", content, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("Expected exactly one Dockerfile syntax directive")
    return content


def write_outputs(**outputs):
    text = "".join(f"{name}={value}\n" for name, value in outputs.items())
    print(text, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(text)


def update(path, dry_run=False):
    original = path.read_text()
    # Resolve everything before writing, so an unavailable image/API leaves all pins intact.
    pins = resolve_pins(read_pins(original))
    frontend = image_pin("docker/dockerfile:1")
    updated = update_content(original, pins, frontend)
    changed = updated != original
    if changed:
        print("".join(difflib.unified_diff(
            original.splitlines(keepends=True), updated.splitlines(keepends=True),
            fromfile=str(path), tofile=str(path),
        )), end="")
        if not dry_run:
            path.write_text(updated)
    write_outputs(changed=str(changed).lower())
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dockerfile", type=Path, default=Path("Dockerfile"))
    args = parser.parse_args()
    update(args.dockerfile, args.dry_run)

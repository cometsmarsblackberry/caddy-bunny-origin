#!/bin/sh
set -eu

image_ref="${1:-caddy-bunny-origin:test}"
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(dirname "$script_dir")

version=$(docker run --rm "$image_ref" caddy version)
case "$version" in
	v2.11.4*) ;;
	*)
		echo "Unexpected Caddy version: $version" >&2
		exit 1
		;;
esac

modules=$(docker run --rm "$image_ref" caddy list-modules)
echo "$modules" | grep -Fx "http.ip_sources.bunny" >/dev/null
echo "$modules" | grep -Fx "dns.providers.bunny" >/dev/null

docker run --rm \
	-v "$repo_dir/tests/Caddyfile.trusted-proxies:/test/Caddyfile:ro" \
	"$image_ref" \
	caddy adapt --config /test/Caddyfile --adapter caddyfile >/dev/null

docker run --rm \
	-e BUNNY_API_KEY=test-only-placeholder \
	-v "$repo_dir/tests/Caddyfile.dns:/test/Caddyfile:ro" \
	"$image_ref" \
	caddy adapt --config /test/Caddyfile --adapter caddyfile >/dev/null

echo "Verified $image_ref ($version) with Bunny trusted-proxy and DNS modules"

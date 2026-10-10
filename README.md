# Caddy Bunny Origin

A minimal Caddy image with Bunny.net support for protected origins:

- [`http.ip_sources.bunny`](https://github.com/digilolnet/caddy-bunny-ip) dynamically supplies Bunny edge IPs to Caddy's `trusted_proxies` configuration.
- [`dns.providers.bunny`](https://github.com/caddy-dns/bunny) enables optional DNS-01 certificate issuance and renewal through Bunny DNS.

The image is independent of any application. Supply your own Caddyfile and persist Caddy's `/data` and `/config` directories as usual.

## Usage

Pin a release or, preferably, an immutable digest in production:

```yaml
services:
  caddy:
    image: ghcr.io/cometsmarsblackberry/caddy-bunny-origin:2.11.4-1
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

Configure Bunny edge addresses as trusted proxies:

```caddyfile
{
	servers {
		trusted_proxies bunny {
			interval 12h
			timeout 15s
		}
		client_ip_headers X-Real-Ip
	}
}
```

This controls whether Caddy trusts the forwarded client-IP header. It does **not** prevent direct connections to the origin; enforce that separately with an IPv4/IPv6 firewall policy.

To use Bunny DNS-01, provide the Bunny API key as a secret and enable the provider:

```caddyfile
{
	acme_dns bunny {env.BUNNY_API_KEY}
}
```

The API key is only required when the DNS module is configured.

## Versioning

Release tags use `<Caddy version>-<image revision>`, for example `2.11.4-1`. The image revision increments when module pins or packaging change without a new Caddy release.

Production deployments should use a release tag or digest. The moving `main` and `latest` tags are intended for testing and discovery.

## Pinned components

The Dockerfile pins:

- Caddy's build version and its builder and runtime image indexes by digest.
- `caddy-bunny-ip` by exact commit.
- `caddy-dns/bunny` by exact commit.
- The stable Dockerfile frontend by digest.

Every published release keeps its exact build inputs. Dependency changes produce a new image release.

## Automatic updates and releases

The `Update dependencies` workflow runs daily and can also be started manually. It resolves the latest stable Caddy release, the latest default-branch commit of each Bunny module, and the current multi-platform digests of the Caddy builder, runtime, and Dockerfile frontend. It validates the updated image before committing the new pins to `main`.

Dependabot checks GitHub Actions daily. Its update PRs are automatically merged after image validation succeeds, including major version updates.

Each new commit on `main` is validated and automatically published as a new `<Caddy version>-<image revision>` release, with images for `linux/amd64` and `linux/arm64`, an SBOM, and provenance attestation. The `main` and `latest` image tags move after a successful build and attestation. Published releases are skipped on reruns; interrupted draft releases are retried. Unchanged dependency checks do not create new commits or releases.

Automation uses the built-in `GITHUB_TOKEN`; no personal access token or separate bot setup is needed. The workflows explicitly request the write permissions they need. If branch/tag protection is added later, it must allow these automated commits, tags, and Dependabot merges. Bot commits and merges explicitly dispatch the build workflow because token-generated pushes do not trigger it.

Servers using a release tag or digest stay on that version until you update their configuration. A failing validation stops that update without changing existing releases.

To preview the upstream changes locally without writing any files:

```bash
python3 scripts/dependencies.py --dry-run
```

## Local verification

```bash
docker build -t caddy-bunny-origin:test .
./scripts/test-image.sh caddy-bunny-origin:test
python3 -m unittest discover -s tests -p 'test_*.py'
```

CI verifies the Caddy version, both compiled modules, and both Caddyfile adapters before publishing multi-platform images with SBOM and provenance metadata.

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

- Caddy `2.11.4` builder and runtime image indexes by digest.
- `caddy-bunny-ip` by exact commit.
- `caddy-dns/bunny` by exact commit.

Dependency updates are reviewed as repository changes and produce a new image release rather than silently replacing an existing release tag.

## Local verification

```bash
docker build -t caddy-bunny-origin:test .
./scripts/test-image.sh caddy-bunny-origin:test
```

CI verifies the Caddy version, both compiled modules, and both Caddyfile adapters before publishing multi-platform images with SBOM and provenance metadata.


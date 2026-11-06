# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e

ARG CADDY_VERSION=2.11.9
ARG CADDY_BUILDER_IMAGE=caddy:2.11.9-builder-alpine@sha256:7d56ec51429d46ff6495db1542cc20e0a4e1559e766b2f4fc48ae25eeca16167
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.9-alpine@sha256:0bbb055bda6793c999bde78b1b5ce3e89f829fb031af2cf50056ea1246559fee

FROM --platform=${BUILDPLATFORM} ${CADDY_BUILDER_IMAGE} AS builder

ARG CADDY_VERSION
ARG BUNNY_IP_VERSION=ef607b8e1644674d5a3df30cbe7d31fe895846ee
ARG BUNNY_DNS_VERSION=13f5878493fabfc95d5d241e069708fc9431451a
ARG TARGETOS
ARG TARGETARCH

RUN CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
    xcaddy build "v${CADDY_VERSION}" \
    --output /usr/bin/caddy \
    --with "github.com/digilolnet/caddy-bunny-ip@${BUNNY_IP_VERSION}" \
    --with "github.com/caddy-dns/bunny@${BUNNY_DNS_VERSION}"

FROM ${CADDY_RUNTIME_IMAGE}

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

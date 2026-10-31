# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e

ARG CADDY_VERSION=2.11.7
ARG CADDY_BUILDER_IMAGE=caddy:2.11.7-builder-alpine@sha256:95a5e7e2692b5eb9545aadc5b90a39f6f509bee59c9508a493f83ee902eaef63
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.7-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5

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

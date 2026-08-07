# syntax=docker/dockerfile:1.7

ARG CADDY_VERSION=2.11.4
ARG CADDY_BUILDER_IMAGE=caddy:2.11.4-builder-alpine@sha256:8e89605351333ad2cc2f3bcc95275a2ccc427f88914050e86a5fde0fd77a63c4
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648

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

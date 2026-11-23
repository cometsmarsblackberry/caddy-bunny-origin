# syntax=docker/dockerfile:1@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183

ARG CADDY_VERSION=2.11.9
ARG CADDY_BUILDER_IMAGE=caddy:2.11.9-builder-alpine@sha256:86e132d1d6db8850352b2dbc15f82a4cb25363ac305ee41e11405873e5931f37
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.9-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0

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

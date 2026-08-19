FROM node:22-alpine AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine

RUN addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app \
    && chown -R app:app /data /config

COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --chown=app:app --from=frontend-builder /build/dist /srv

USER 10001:10001
EXPOSE 80 443 443/udp

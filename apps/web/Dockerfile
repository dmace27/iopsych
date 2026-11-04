FROM node:22-bookworm-slim AS build
WORKDIR /opt/iopsych
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY packages/eslint-glob packages/eslint-glob
RUN npm ci
COPY tsconfig.base.json ./
COPY packages/shared packages/shared
COPY apps/web apps/web
COPY apps/api/tests/fixtures/report_trace apps/api/tests/fixtures/report_trace
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim AS runtime
ARG REVISION=unknown
LABEL org.opencontainers.image.revision=$REVISION
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /opt/iopsych
COPY --from=build /opt/iopsych/package.json ./
COPY --from=build /opt/iopsych/node_modules node_modules
COPY --from=build /opt/iopsych/packages packages
COPY --from=build --chown=node:node /opt/iopsych/apps/web apps/web
WORKDIR /opt/iopsych/apps/web
USER node
EXPOSE 3000
STOPSIGNAL SIGTERM
# Direct Node execution delivers signals without an npm/shell parent.
CMD ["node", "../../node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]

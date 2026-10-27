FROM node:24.18.1-bookworm-slim@sha256:235600a8101ab264e117b1768e925532262668dc9b581ef1dd7d96ced463b8e7 AS deps
WORKDIR /app
ENV COREPACK_HOME=/opt/corepack
RUN corepack enable && corepack prepare pnpm@10.28.2 --activate
RUN mkdir -p /opt/corepack && chown -R node:node /opt/corepack
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/openapi.json packages/contracts/openapi.json
RUN pnpm install --frozen-lockfile

FROM deps AS build
COPY --chown=node:node apps/web apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter web build

FROM deps AS fixture-dev
COPY --chown=node:node apps/web apps/web
RUN chown -R node:node /app/apps/web /opt/corepack
ENV NEXT_TELEMETRY_DISABLED=1 TASTEDUEL_FIXTURES=1
USER node
EXPOSE 3000
CMD ["pnpm", "--filter", "web", "dev"]

FROM node:24.18.1-bookworm-slim@sha256:235600a8101ab264e117b1768e925532262668dc9b581ef1dd7d96ced463b8e7
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]

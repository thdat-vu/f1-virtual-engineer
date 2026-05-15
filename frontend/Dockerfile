# ──────────────────────────────────────────────────────────────
# Stage 1 — deps: clean install with the lockfile-free package.json.
#                 npm ci would be ideal but the repo doesn't track
#                 package-lock.json (see .gitignore), so npm install
#                 is the honest choice.
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json ./package.json
RUN npm install --no-audit --no-fund --prefer-offline

# ──────────────────────────────────────────────────────────────
# Stage 2 — builder: compile Next with standalone output.
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend .
ARG NEXT_PUBLIC_API_BASE_URL=/api
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ──────────────────────────────────────────────────────────────
# Stage 3 — runtime: ships only Next's standalone bundle (server +
#                    minimal node_modules) plus public/ and the
#                    static chunks. No source, no devDependencies.
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Drop privileges — alpine doesn't ship a `node` user by default,
# so create one rather than running as root.
RUN addgroup -S app && adduser -S app -G app
USER app

COPY --from=builder --chown=app:app /app/public ./public
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static

EXPOSE 3000

# Standalone server.js bundles all required deps; no `npm start` needed.
CMD ["node", "server.js"]

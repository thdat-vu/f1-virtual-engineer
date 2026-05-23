# ──────────────────────────────────────────────────────────────
# Stage 1 — deps: corepack pins yarn from package.json's
#                 packageManager field, so dev/CI/Docker all run
#                 the exact same Yarn 4. --immutable enforces the
#                 committed yarn.lock — no resolution drift.
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml ./
RUN yarn install --immutable

# ──────────────────────────────────────────────────────────────
# Stage 2 — builder: compile Next with standalone output.
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY frontend .
ARG NEXT_PUBLIC_API_BASE_URL=/api
ARG BACKEND_INTERNAL_URL=http://backend:8000
# NEXT_PUBLIC_* must be present at `next build` time — Next inlines
# them into the client JS bundle here, not at runtime. Mounting them
# only via env_file on the runtime container is too late: the bundle
# is already shipped, the values aren't in it, and the auth flow
# silently disables itself in prod. No defaults — empty values would
# build a broken bundle without complaining.
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
ENV NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL}
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY}
ENV NEXT_TELEMETRY_DISABLED=1
RUN yarn build

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

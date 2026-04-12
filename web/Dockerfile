# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS deps

WORKDIR /app

COPY web/package.json ./package.json

RUN npm install --no-fund --no-audit

FROM node:24-bookworm-slim AS builder

WORKDIR /app

ARG SCANNER_API_INTERNAL_URL=http://api:8000
ARG NEXT_PUBLIC_SCANNER_API_BASE_URL=/scanner-api
ARG NEXT_PUBLIC_SCANNER_API_MODE=live

ENV SCANNER_API_INTERNAL_URL=${SCANNER_API_INTERNAL_URL}
ENV NEXT_PUBLIC_SCANNER_API_BASE_URL=${NEXT_PUBLIC_SCANNER_API_BASE_URL}
ENV NEXT_PUBLIC_SCANNER_API_MODE=${NEXT_PUBLIC_SCANNER_API_MODE}

COPY --from=deps /app/node_modules ./node_modules
COPY web ./

RUN npm run build

FROM node:24-bookworm-slim AS runner

WORKDIR /app

ARG SCANNER_API_INTERNAL_URL=http://api:8000
ARG NEXT_PUBLIC_SCANNER_API_BASE_URL=/scanner-api
ARG NEXT_PUBLIC_SCANNER_API_MODE=live

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV SCANNER_API_INTERNAL_URL=${SCANNER_API_INTERNAL_URL}
ENV NEXT_PUBLIC_SCANNER_API_BASE_URL=${NEXT_PUBLIC_SCANNER_API_BASE_URL}
ENV NEXT_PUBLIC_SCANNER_API_MODE=${NEXT_PUBLIC_SCANNER_API_MODE}

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]

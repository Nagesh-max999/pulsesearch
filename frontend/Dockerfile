FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci is stricter but fails here on optional platform-specific packages
# (lightningcss/@napi-rs native bindings) that differ between the host OS the
# lockfile was generated on and this Alpine/Linux build image.
RUN npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]

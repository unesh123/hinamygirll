FROM node:22-alpine AS build
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY apps/desktop/package.json apps/desktop/
COPY packages ./packages
RUN pnpm install --frozen-lockfile --filter ./apps/web...
COPY apps/web apps/web
RUN pnpm --dir apps/web build

FROM nginx:1.27-alpine
COPY infra/compose/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html

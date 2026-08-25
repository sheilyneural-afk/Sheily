FROM node:24-alpine AS build

ARG APP_NAME
ARG VITE_SHEILY_API_URL=http://localhost:8101
ENV VITE_SHEILY_API_URL=${VITE_SHEILY_API_URL}
WORKDIR /src
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/typescript/contracts packages/typescript/contracts
COPY apps/${APP_NAME} apps/${APP_NAME}
RUN pnpm install --frozen-lockfile
RUN pnpm --filter "@noosfera/${APP_NAME}" build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
ARG APP_NAME
COPY --from=build /src/apps/${APP_NAME}/dist /usr/share/nginx/html
EXPOSE 8080

FROM node:25-alpine AS build
WORKDIR /app
COPY package*.json ./
# The package postinstall initializes MSW in public/, so create it before dependency installation.
RUN mkdir -p public && npm install --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=/api
ARG VITE_USE_MOCKS=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_USE_MOCKS=$VITE_USE_MOCKS
RUN npm run build

FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN mkdir -p /etc/nginx/snippets
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q --spider http://127.0.0.1/ || exit 1

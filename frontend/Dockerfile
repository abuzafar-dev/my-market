# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_API_URL is baked into the static build at build time (Vite env
# vars aren't readable at container runtime) — pass it as a build arg
# from docker-compose.yml or your CI build step.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# NeceCity frontend image - multi-stage build.
# Stage 1 builds the static Vite bundle; stage 2 serves it with nginx.

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

# VITE_API_BASE_URL is baked into the JS bundle at build time (Vite env
# vars are compile-time, not runtime) - pass it as a build arg from
# docker-compose.yml so it can differ per deployment without editing code.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

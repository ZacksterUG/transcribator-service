FROM node:20-alpine AS builder

ARG VITE_WS_URL

WORKDIR /app

ENV VITE_WS_URL=$VITE_WS_URL

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

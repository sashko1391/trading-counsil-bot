FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Serve with lightweight static server
FROM node:22-slim
RUN npm install -g serve
WORKDIR /app
COPY --from=build /app/dist ./dist

ENV PORT=3000
EXPOSE ${PORT}
CMD ["serve", "-s", "dist", "-l", "3000"]

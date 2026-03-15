FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Lightweight static server (nginx would be better but serve keeps it simple)
FROM node:22-slim
RUN npm install -g serve@14
WORKDIR /app
COPY --from=build /app/dist ./dist

USER node
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]

FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY tsconfig.json ./
COPY src ./src

ENV PORT=8003
EXPOSE 8003

CMD ["npx", "tsx", "src/index.ts"]

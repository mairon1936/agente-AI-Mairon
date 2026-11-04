FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.js durable-queue.js ./
COPY public ./public

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000 \
    BRIDGE_DATA_DIR=/data/bridge

USER node
EXPOSE 3000
CMD ["node", "server.js"]

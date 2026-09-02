FROM node:20-slim
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY src ./src
EXPOSE 4000
CMD ["sh", "-c", "node src/worker.js & node src/server.js"]

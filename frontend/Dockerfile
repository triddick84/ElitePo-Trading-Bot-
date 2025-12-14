FROM node:16-alpine

# Set working directory
WORKDIR /app/frontend

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Run application
CMD ["yarn", "start"]

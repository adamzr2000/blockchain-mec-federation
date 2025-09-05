# Use official lightweight Node.js image
FROM node:20-alpine

# Install bash, git, and Docker CLI for completeness
RUN apk add --no-cache bash git

# Install quorum-dev-quickstart globally
RUN npm install -g quorum-dev-quickstart@0.2.4

# Set working directory inside the container
WORKDIR /workspace
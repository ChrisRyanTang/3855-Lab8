FROM node:16-alpine

# Set working directory
WORKDIR /app

# Add `/app/node_modules/.bin` to $PATH
ENV PATH /app/node_modules/.bin:$PATH

# Install npm@8 for compatibility
RUN npm install -g npm@8

# Install app dependencies
COPY package.json ./
COPY package-lock.json ./
RUN npm install

# Install react-scripts globally for the build process
RUN npm install react-scripts@3.4.1 -g

# Copy app files
COPY . ./

# Build the app for production
RUN npm run build

# Install `serve` to serve the production build
RUN npm install -g serve

# Expose the desired port (change if necessary)
EXPOSE 3000

# Command to serve the build
CMD ["serve", "-s", "build", "-l", "3000"]

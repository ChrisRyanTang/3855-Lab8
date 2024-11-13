FROM node:16-alpine

# Set working directory
WORKDIR /app

# Add `/app/node_modules/.bin` to $PATH
ENV PATH /app/node_modules/.bin:$PATH

# Install app dependencies
COPY package.json ./
COPY package-lock.json ./

# Install npm@8 to ensure compatibility
RUN npm install -g npm@8

# Install project dependencies
RUN npm install

RUN npm install react-scripts@3.4.1 -g
# add app

# Copy app files
COPY . ./

# Start app
CMD ["npm", "start"]

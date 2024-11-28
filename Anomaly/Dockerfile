FROM ubuntu:22.04

LABEL maintainer="ctang93@my.bcit.ca"

# Update system and install Python
RUN apt-get update -y && \
    apt-get install -y python3 python3-pip && \
    pip3 install --upgrade pip

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY ./requirements.txt /app/requirements.txt

# Install dependencies
RUN pip3 install -r requirements.txt

# Copy the application source code
COPY . /app

# Expose the application's port
EXPOSE 8120

# Define the container's entry point
ENTRYPOINT ["python3"]
CMD ["app.py"]

FROM ubuntu:22.04

LABEL maintainer="ctang93@my.bcit.ca"

RUN apt-get update -y && \
    apt-get install -y python3 python3-pip && \
    pip3 install --upgrade pip

# Copy requirements and install dependencies
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip3 install -r requirements.txt

# Copy the source code
COPY . /app

ENTRYPOINT ["python3"]
CMD ["app.py"]

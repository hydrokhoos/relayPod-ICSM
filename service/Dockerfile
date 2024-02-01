# docker build -t relay-service:test .
FROM ubuntu:latest

RUN apt update
RUN apt install python3 pip -y

COPY ./src /src
COPY ./requirements.txt /requirements.txt
RUN pip install -r requirements.txt

WORKDIR /src
CMD ["python3", "service.py"]

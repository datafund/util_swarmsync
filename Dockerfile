FROM ubuntu:20.04

RUN apt-get update && apt-get install -y software-properties-common binutils
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.8 python3.8-dev python3.8-venv python3-pip
RUN python3.8 -m venv /venv 

COPY *.py .
COPY requirements.txt .

RUN export PATH=/venv/bin:$PATH; python -m pip install -r requirements.txt pyinstaller && \
  pyinstaller --paths=/venv --onefile swarmsync.py

FROM ubuntu:20.04

RUN apt-get update && apt-get install -y software-properties-common binutils
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt-get install -y python3.10 python3.10-dev python3.10-venv python3-pip
RUN python3.10 -m venv /venv

COPY *.py ./
COPY requirements.txt .

RUN export PATH=/venv/bin:$PATH; python -m pip install -r requirements.txt pyinstaller && \
  pyinstaller --paths=/venv --onefile swarmsync.py

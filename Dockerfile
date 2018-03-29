FROM python:3.5

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

ENTRYPOINT ["/bin/bash", "run.sh"]

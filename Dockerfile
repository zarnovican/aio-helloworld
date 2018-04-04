FROM python:3.6-alpine

WORKDIR /usr/src/app

RUN apk add --update \
    curl \
  && rm -rf /var/cache/apk/*

HEALTHCHECK --interval=5s --start-period=1m CMD curl -A healthcheck --max-time 3 --fail http://localhost:80/ping || exit 1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG VERSION=devel
ENV VERSION=$VERSION

ENTRYPOINT ["python", "./aio-helloworld.py"]

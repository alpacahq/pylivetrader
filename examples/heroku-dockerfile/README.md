# Using Docker & Pylivetrader to deploy an algo

## You will need:

---
### Github Setup

Repo with (NOTE: DO NOT REPLACE ANY KEYS OR IDS IN THIS SECTION!):

> algo.py
```
Example here: https://github.com/alpacahq/pylivetrader/blob/master/examples/MACD/macd_example.py
```

> Dockerfile
```
FROM alpacamarkets/pylivetrader

ARG APCA_API_SECRET_KEY
ARG APCA_API_KEY_ID
ARG APCA_API_BASE_URL

ENV APCA_API_SECRET_KEY=$APCA_API_SECRET_KEY
ENV APCA_API_KEY_ID=$APCA_API_KEY_ID
ENV APCA_API_BASE_URL=$APCA_API_BASE_URL

RUN mkdir /app

COPY . /app

WORKDIR /app

CMD pylivetrader run -f algo.py
```

> heroku.yml
```
build:
  config:
    APCA_API_KEY_ID: $APCA_API_KEY_ID
    APCA_API_SECRET_KEY: $APCA_API_SECRET_KEY
  docker:
    worker: Dockerfile

run:
  worker:
    image: worker
```

Push repository to github.com (follow instructions there if needed)

---

## Heroku Setup

1. Login (create account if needed)
2. Create New App (New > Create App)
   * you can name it anything unique
3. Find 'Deployment method' on 'Deploy' tab
4. Choose Github and connect
5. Once initial deploy completes see 'Resources' tab and enable the worker
6. Under `Settings` tab find `Config Vars`
7. Update Config Vars with
```
APCA_API_SECRET_KEY = {{YOUR APCA_API_SECRET_KEY}}
APCA_API_KEY_ID = {{YOUR APCA_API_KEY_ID}}
APCA_API_BASE_URL = {{APCA_API_BASE_URL paper-api.alpaca.markets or api.alpaca.markets}}
```
(would recommend you start with paper)


If you have questions or comments please visit the slack channel: #algo-deployment




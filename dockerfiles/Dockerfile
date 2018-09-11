FROM python:3.6-stretch

RUN pip install pipenv

ADD Pipfile Pipfile.lock /tmp/

ADD Pipfile Pipfile.lock /

RUN pipenv install --system --dev
FROM python:3.6

RUN pip install pipenv

ADD Pipfile Pipfile.lock /

RUN pipenv install --system

ADD algo.py /work/algo.py

WORKDIR /work

CMD ["pylivetrader", "run", "-f", "/work/algo.py"]
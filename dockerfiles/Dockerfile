FROM python:3.6-stretch

# Install talib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
  tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --prefix=/usr && \
  make && \
  make install
RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz

RUN pip install pipenv

ADD Pipfile Pipfile.lock /tmp/
ADD Pipfile Pipfile.lock /

RUN pipenv install --system --dev

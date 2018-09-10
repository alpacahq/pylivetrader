# Working Example to Run Quantopian Algorithm in Live

This directory contains an actual algorithm code that is converted
from Quantopian source to pylivetrader code. [original.py](./original.py) is
the code from Quantopian and you can still copy & paste it
to your backtest IDE to see how it performs in the testing.

[algo.py](./algo.py) is the output of the conversion following
[the migration document](../../migration.md) ready for
live trading. It comes with [Pipfile](./Pipfile) files so if you have
[pipenv](https://pipenv.readthedocs.io/) installed in your
environment, you can immediately start.


## How to Run your Algorithm
All you need to do is to set broker setting, and if you are
using Alpaca (default), you can set the following.

```sh
export APCA_API_KEY_ID=xxx
export APCA_API_SECRET_KEY=yyy
```

After you configured the setting, launch the algorithm by

```sh
pylivetrader run -f ./algo.py
```

## Deployment
There are a number of ways to deploy your algorithm but
here we show how to deploy to [Heroku](https://heroku.com).

Heroku offers a free tier worker dyno that runs a program
for long time as far as the computation is not too heavy,
or you can pay as little as a few dollars a month.

Create your Heroku account if not yet, and you install
the `heroku` command line tool. Then all you need to do is
described [here](https://devcenter.heroku.com/articles/git),
You can create a new git repository here by `git init`
and follow the instruction to "push" to Heroku.

You will need to configure the environment variables
in Heroku dashboard settings.

Lastly, start your worker dyno by

```sh
heroku ps:scale worker=1
```

### Alternative
This directory comes with Dockerfile and you can run
this docker container anywhere too. Make sure
you set up your API key through environment variables.
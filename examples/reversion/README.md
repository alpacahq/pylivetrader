# Paper Trading Quantopian algorithm with Alpaca and AWS Elastic Beanstalk
This directory contains an Alpaca migrated [Mean-Reversion Long Quantopian algorithm](https://www.quantopian.com/posts/mean-reversion-long-for-alpacas-pylivetrader).
It uses a Custom Backend. Does not use alpaca.py backend as it only works if the account can live trade (it makes use of the polygon API which is not available for non live trading accounts).

[reversion_original.py](./reversion_original.py) is the backtested original Quantopian algorithm.\
[reversion.py](./reversion.py) is the Quantopian algorithm migrated to run with Alpaca.\
[paper.py](./paper.py) is the backend used for paper trading with Alpaca.\
[migration document](../../migration.md) to migrate the Quantopian algorithm to Alpaca.


## How to Deploy and Run the Algorithm
Deploying the algorithm in the cloud is really easy. All you need to do is to upload the [Dockerrun.aws.json](./Dockerrun.aws.json) to your Elastic Beanstalk Console. You can also build the docker images yourself and host them using a [Docker Hub](https://hub.docker.com) account (more details on running apps in the cloud with Elastic Beanstalk and Docker [here](https://docker-curriculum.com/)).
In both cases you will also have to [set the required environment variables:](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/environments-cfg-softwaresettings.html#environments-cfg-softwaresettings-console)

```sh
APCA_API_KEY_ID=xxx
APCA_API_SECRET_KEY=yyy
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

## Alternative Deploy
As an alternative to AWS Elastic Beanstalk, you can use the Dockerfiles to build and run the container anywhere you want. 

### Dockerfiles to build the images
[DockerfileBase](./DockerfileBase) creates the base image to run algorithms.\
[DockerfileReversion](./DockerfileReversion) creates the image with the mean reversion long algorithm. This is the one that runs the algo. When running it, remember to add an env file:
```sh
docker build -f DockerfileReversion -t [repository]/[image_name]:[version] .
docker run --env-file ./my_env  -P --name [name] [repository]/[image_name]:[version]
```
Where my_env contains:
```sh
APCA_API_KEY_ID=xxx
APCA_API_SECRET_KEY=yyy
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```
[DockerfileTests](./DockerfileTests) creates the image to run the unit tests of the algorithm.



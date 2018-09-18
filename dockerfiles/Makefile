TAG := $(shell grep pylivetrader Pipfile | sed  -E 's/pylivetrader = "==([0-9.]+)"/\1/')

ifeq ($(TAG),)
	error "TAG is not specified"
endif

all:
	docker build -t alpacamarkets/pylivetrader:$(TAG) .

push:
	docker push alpacamarkets/pylivetrader:$(TAG)
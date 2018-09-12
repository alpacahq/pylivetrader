ifeq ($(TAG),)
	error "TAG is not specified"
endif

all:
	docker build -t alpacamarkets/pylivetrader:$(TAG) .

push:
	docker push alpacamarkets/pylivetrader:$(TAG)
image:
	docker build -t pylivetrader .

shell:
	docker run -it --rm -v $(PWD):/w -w /w pylivetrader bash

shell:
	docker run -it --rm -v $(PWD):/w -w /w python:3.6-stretch bash

lint:
	python setup.py flake8

test:
	python setup.py test

release:
	python setup.py sdist bdist_wheel
	twine upload dist/*

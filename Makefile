
.PHONY: freeze image

freeze:
	pip freeze | grep -v helloworld > requirements.txt

image:
	docker build -t aio-helloworld .

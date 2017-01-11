
.PHONY: freeze image tag

freeze:
	pip freeze | grep -v helloworld > requirements.txt

image:
	docker build -t zarnovican/aio-helloworld .

tag:
	docker tag zarnovican/aio-helloworld zarnovican/aio-helloworld:$(shell python setup.py --version | tr + _)

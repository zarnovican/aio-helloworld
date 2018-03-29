
.PHONY: image tag

image:
	docker build -t zarnovican/aio-helloworld .

tag:
	docker tag zarnovican/aio-helloworld zarnovican/aio-helloworld:$(shell python setup.py --version | tr + _)

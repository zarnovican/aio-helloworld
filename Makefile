
VERSION = $(shell git describe --match '[0-9]*' --dirty)

.PHONY: image

image:
	docker build \
		--build-arg VERSION=$(VERSION) \
		--label image.version=$(VERSION) \
		-t zarnovican/aio-helloworld:latest \
		-t zarnovican/aio-helloworld:$(VERSION) \
		.

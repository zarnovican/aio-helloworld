
.PHONY: freeze

freeze:
	pip freeze | grep -v helloworld > requirements.txt

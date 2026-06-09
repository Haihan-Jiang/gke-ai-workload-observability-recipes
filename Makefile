PYTHON ?= python3

.PHONY: help evidence validate ci test demo kind-smoke clean

help:
	@printf '%s\n' \
		'Targets:' \
		'  make evidence    regenerate committed evidence' \
		'  make validate    run the full local validation gate' \
		'  make ci          run the CI-mode evidence stability gate' \
		'  make test        run the unittest suite only' \
		'  make demo        run the local incident replay demo' \
		'  make kind-smoke  run the optional kind/Kubernetes smoke test' \
		'  make clean       remove generated local output under out/'

evidence:
	./scripts/generate-evidence.sh

validate:
	./scripts/validate.sh

ci:
	CI=true ./scripts/validate.sh

test:
	$(PYTHON) -m unittest discover -s tests

demo:
	./scripts/run-local-demo.sh

kind-smoke:
	./scripts/kind-smoke.sh

clean:
	rm -rf out

EXPS = semi hemi soho temi

all: mpspdz $(EXPS)

exps: $(EXPS)

mpspdz:
	docker build --tag mpspdz \
			--file deps/mpspdz.Dockerfile \
			deps/MP-SPDZ

circuits:
	docker build -t expbase \
		--target expbase \
		.

$(EXPS): 
	docker build -t exp:$@ \
		--target exp \
		--build-arg machine=$@-party.x \
		.

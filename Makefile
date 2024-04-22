all: exps

deps-init:
	git submodule update --init

exps: deps-init
	make -C mpspdz
	make -C helium


.PHONY: helium mpspdz deps-init all

helium:
	make -C helium

deps-init:
	git submodule update --init

mpspdz: deps-init
	make -C mpspdz
	
all: helium mpspdz
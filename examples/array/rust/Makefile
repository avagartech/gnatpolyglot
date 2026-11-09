
LIB_NAME=ex2

include ../../rust.mk

INPUT_PROXY=$(CURDIR)/../2proxy/

RUST_PROXY=$(CURDIR)/../2rust/

main:
	# Build the bindings
	$(GPRBUILD) "$(INPUT_PROXY)/$(LIB_NAME)-proxy-agg.gpr" $(PROXY_BUILD_FLAGS)
	POLYGLOT_PROXY_LIB_DIR="$(INPUT_PROXY)/lib_agg/static/dev/" \
	POLYGLOT_PROXY_LIB_NAME=$(LIB_NAME)_proxy_agg \
	cargo run

# Shared build settings for the Rust examples.
ifeq ($(shell uname -s),Darwin)
GPRBUILD ?= gprbuild
PROXY_BUILD_FLAGS += -XLIBRARY_STANDALONE=standard
export POLYGLOT_ADA_COMPILER ?= gcc
else
GPRBUILD ?= gprbuild2
endif

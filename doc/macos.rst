.. _macos:

Experimental Apple Silicon macOS support
========================================

Scope
-----

This port covers the Rust output backend and macOS library discovery in the
JVM launcher, installed native wrapper, and native-image build configuration.
The Rust backend remains experimental. The macOS integration smoke test
exercises real Ada code and generated Rust bindings on Apple Silicon. The
initial macOS target is native arm64 (``aarch64-apple-darwin``); Intel macOS
support is deferred to a later phase.
The Java output backend is still outside this port's scope.

The initial validation used macOS 26.5.2 on arm64, GNAT 16.1.0, GPRbuild
26.0.0, GraalVM JDK 24.0.2, Maven 3.9.9, and Rust/Cargo 1.97.0 nightly.
The independent Maven build passed its ten unit tests; both new
platform tests passed, and the installed Ada wrapper was compiled and checked
with a native worker. The complete scanner/native-image build has not been
validated because compatible Libadalang Java bindings were not installed.

Prerequisites
-------------

Use native arm64 tools and libraries throughout, targeting Apple Silicon
``aarch64-apple-darwin``. Install:

* Xcode Command Line Tools (including the macOS SDK and linker).
* GNAT and GPRbuild for Apple Silicon.
* JDK 24 and Maven. Use GraalVM JDK 24 for native-image builds.
* Libadalang **with its Java bindings installed in Maven**, built from a
  version compatible with this GNATpolyglot checkout. Follow the
  `Libadalang build instructions
  <https://docs.adacore.com/live/wave/libadalang/html/libadalang_ug/building.html>`_.
  An Ada-only or Python-only Libadalang installation is insufficient.
* Rust and Cargo for the same target.
* Python 3.11 or later, PyYAML, and e3-testsuite for the testsuite.

Put the GNAT and GPRbuild binaries before the Apple compiler tools on ``PATH``.
Set ``JAVA_HOME`` and ``GRAAL_HOME`` to the JDK's ``Contents/Home`` directory.
Set ``POLYGLOT_ADA_COMPILER`` to the full path to the target GNAT ``gcc``;
Apple's ``/usr/bin/gcc`` is Clang and cannot locate the Ada runtime archives.
For example, adapting the installation paths:

.. code:: sh

   export JAVA_HOME="/path/to/graalvm/Contents/Home"
   export GRAAL_HOME="$JAVA_HOME"
   export PATH="/path/to/gnat/bin:/path/to/gprbuild/bin:$JAVA_HOME/bin:$PATH"
   export POLYGLOT_ADA_COMPILER="/path/to/gnat/bin/gcc"
   export GNATPOLYGLOT_RUNTIME="$PWD/gnatpolyglot/runtimes"

Choose ``MACOSX_DEPLOYMENT_TARGET`` consistently for the Ada and Rust builds,
at least as new as the minimum required by your compiler's runtime and native
dependencies. For local testing it may be set to the current macOS version:

.. code:: sh

   export MACOSX_DEPLOYMENT_TARGET="$(sw_vers -productVersion)"

Building the generator
----------------------

Point ``C_INCLUDE_PATH`` to the directory containing ``libadalang.h`` and
``LIBRARY_PATH`` to the directories containing ``libadalang.dylib`` and its
dependencies. Export ``DYLD_LIBRARY_PATH`` for dynamic library loading as well.
Some system launchers strip ``DYLD_*`` variables; the JVM launcher also reads
``LIBRARY_PATH`` on macOS when constructing ``java.library.path``.

.. code:: sh

   export C_INCLUDE_PATH="/path/to/libadalang/include"
   export LIBRARY_PATH="/path/to/libadalang/lib:/path/to/other/dependency/lib"
   export DYLD_LIBRARY_PATH="$LIBRARY_PATH"
   mvn package -f gnatpolyglot/pom.xml
   python3 gnatpolyglot/cli/gnatpolyglot.py --help

The optional native build uses ``libadalang.dylib`` and Apple linker run paths,
and gets zlib from the macOS SDK:

.. code:: sh

   mvn package -f gnatpolyglot/pom.xml -Pnative -Dconfig.python=python3

Building Ada and Rust bindings
------------------------------

Some Darwin GNAT/GPRbuild combinations reject ``encapsulated`` standalone
libraries. Build a **standard** standalone static proxy instead and let the
generated Rust crate bundle the target GNAT runtime archives. With
``POLYGLOT_ADA_COMPILER`` set as above:

.. code:: sh

   python3 gnatpolyglot/cli/gnatpolyglot.py ada2proxy \
       -P examples/hello-world/ex0.gpr -o /tmp/ex0-proxy
   python3 gnatpolyglot/cli/gnatpolyglot.py proxy2rust \
       /tmp/ex0-proxy/proxy.json -o /tmp/ex0-rust
   gprbuild -P /tmp/ex0-proxy/ex0-proxy-agg.gpr \
       -XLIBRARY_STANDALONE=standard
   POLYGLOT_PROXY_LIB_DIR=/tmp/ex0-proxy/lib_agg/static/dev \
   POLYGLOT_PROXY_LIB_NAME=ex0_proxy_agg \
       cargo build --manifest-path /tmp/ex0-rust/Cargo.toml

The Rust build script queries the compiler for ``adalib/libgnarl.a`` and
``adalib/libgnat.a``. It also includes ``libemutls_w.a`` when present, since
GCC-built C thread-local storage can require it on Darwin. The standard
standalone library retains automatic Ada elaboration. This path assumes the
normal full GNAT runtime; custom/restricted runtimes need separate work.

Validation without Libadalang
-----------------------------

The platform checks and the macOS Rust integration test can be run before
installing Libadalang. Build only the independent proxy and Rust generator
modules first:

.. code:: sh

   mvn package -f gnatpolyglot/pom.xml -pl proxy2rust -am
   python3 testsuite/testsuite.py platform_support macos_rust

The macOS test uses a fixed proxy description for a small Ada library, renders
a complete Rust crate using the actual generator, builds the standard Ada
aggregate archive, and runs a separate Cargo binary consuming the generated
crate. It checks scalar calls, automatic elaboration, nonzero array bounds,
floating-point arrays, UTF-8 strings, and destruction. It deliberately does
not exercise Ada2Proxy or Libadalang. Native-image dependency discovery is
covered by configuration tests; building the complete CLI/native image still
requires Libadalang's native libraries and Java bindings.

With compatible Libadalang and a GPRbuild supporting the testsuite's
``--gpr=2`` interface installed, run the existing Rust tests too:

.. code:: sh

   export PATH="$PWD/gnatpolyglot/cli:$PATH"
   python3 testsuite/testsuite.py rust

macOS Rust tests are enabled for Apple Silicon (``aarch64-darwin``). Java output
tests retain their existing platform restriction. This port does not add
32-bit, embedded, or ``no_std`` support.

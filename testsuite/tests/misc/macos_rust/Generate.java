// Copyright (C) 2026, AdaCore
// SPDX-License-Identifier: GPL-3.0-or-later

import com.adacore.gnatpolyglot.proxy2rust.RustPrinter;
import java.nio.file.Path;

class Generate {
    public static void main(String[] args) throws Exception {
        new RustPrinter(Path.of(args[0]))
                .generate(Path.of(args[1]).toAbsolutePath(), Path.of(args[2]).toAbsolutePath());
    }
}

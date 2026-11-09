//
//  Copyright (C) 2025-2026, AdaCore
//  SPDX-License-Identifier: GPL-3.0-or-later
//

package com.adacore.gnatpolyglot.proxy2rust;

import com.adacore.gnatpolyglot.proxy.GNATpolyglotSetup;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.Callable;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;
import picocli.CommandLine.Parameters;

@Command(name = "proxy2rust", description = "Create the Rust interface of a proxy representation")
public class Proxy2Rust implements Callable<Integer> {

    /** Run the Rust generator independently of the Ada scanner and Libadalang. */
    public static void main(String[] args) {
        System.exit(new CommandLine(new Proxy2Rust()).execute(args));
    }

    @Parameters(index = "0", paramLabel = "proxy_file", description = "input proxy json file")
    Path proxyFile;

    @Option(
            names = {"-o", "--output"},
            description =
                    "path to the directory in which the Rust interface should be generated."
                            + " Directories along the path are created if they do not exist yet.",
            required = true)
    Path outputPath;

    @Option(
            names = {"-h", "--help"},
            usageHelp = true,
            description = "display sub-command usage and exit")
    boolean helpRequested;

    @Option(
            names = {"--with-runtime"},
            description =
                    "location of the GNATpolyglot runtime to use. Defaults to"
                            + " <outputPath>/runtimes")
    Path withRuntime;

    @Option(
            names = {"--embedded"},
            description = "generate a runtime-free no_std crate for scalar C ABI functions")
    boolean embedded;

    @Override
    public Integer call() throws Exception {
        if (embedded && withRuntime != null) {
            System.err.println("--embedded cannot be combined with --with-runtime");
            return 1;
        }
        RustPrinter printer = new RustPrinter(proxyFile, embedded);

        try {
            Files.createDirectories(outputPath);
        } catch (FileAlreadyExistsException e) {
            System.err.println("%s is not a directory".formatted(e.getMessage()));
            return 1;
        }

        if (!embedded && withRuntime == null) {
            withRuntime = outputPath.resolve("runtimes");
            new GNATpolyglotSetup(
                            withRuntime,
                            Files.isDirectory(withRuntime),
                            GNATpolyglotSetup.Lang.valueOf(printer.getProxy().inputLanguage),
                            GNATpolyglotSetup.Lang.rust,
                            true)
                    .call();
        }

        printer.generate(outputPath, withRuntime);

        return 0;
    }
}

//
//  Copyright (C) 2025-2026, AdaCore
//  SPDX-License-Identifier: GPL-3.0-or-later
//

package com.adacore.gnatpolyglot.proxy2rust;

import com.adacore.gnatpolyglot.Printer;
import com.adacore.gnatpolyglot.proxy.Name;
import com.adacore.gnatpolyglot.proxy.ProxyException;
import gg.jte.ContentType;
import gg.jte.TemplateEngine;
import gg.jte.output.FileOutput;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

public class RustPrinter extends Printer {

    /** The template rendering engine. */
    private final TemplateEngine templateEngine =
            TemplateEngine.createPrecompiled(
                    Path.of("jte-classes"),
                    ContentType.Plain,
                    RustPrinter.class.getClassLoader(),
                    "gg.jte.generate.precompiled.proxy2rust");

    public RustPrinter(Path path) throws IOException, ProxyException {
        super(path);
    }

    @Override
    public void generate(Path outputPath, Path runtimeLocation) throws IOException {
        outputPath = outputPath.toAbsolutePath().normalize();
        Files.createDirectories(outputPath);
        RustAPI api = new RustAPI(context, proxy.name);

        Path runtime = runtimeLocation.toAbsolutePath().normalize().resolve("ada/src2rust");
        String dependencyPath;
        try {
            dependencyPath = outputPath.relativize(runtime).toString();
        } catch (IllegalArgumentException e) {
            // Windows installations may put the runtime on another drive.
            dependencyPath = runtime.toString();
        }
        String runtimeDependency =
                com.adacore.gnatpolyglot.proxy.Proxy.getObjectMapper()
                        .writeValueAsString(dependencyPath.replace(File.separatorChar, '/'));

        // Generate Cargo.toml. Hand the template the installed runtime location (relative to the
        // generated crate); the template knows where the runtime crate it depends on sits within
        // that layout.
        Path cargoToml = outputPath.resolve("Cargo.toml");
        try (FileOutput out = new FileOutput(cargoToml)) {
            templateEngine.render(
                    "cargo_toml.jte",
                    Map.of("api", api, "proxy", proxy, "runtimeLocation", runtimeDependency),
                    out);
        }

        // Generate build.rs
        Path buildRs = outputPath.resolve("build.rs");
        try (FileOutput out = new FileOutput(buildRs)) {
            templateEngine.render("build_rs.jte", Map.of("api", api, "proxy", proxy), out);
        }

        // Record element types that need a generated PolyglotArrayElement impl (empty for
        // native-only or array-free proxies).
        var recordArrayElements = api.recordArrayElements(proxy.modules);

        // Generate src/lib.rs
        Path srcDir = outputPath.resolve("src");
        Files.createDirectories(srcDir);
        Path libRs = srcDir.resolve("lib.rs");
        try (FileOutput out = new FileOutput(libRs)) {
            templateEngine.render(
                    "lib_rs.jte",
                    Map.of(
                            "api",
                            api,
                            "proxy",
                            proxy,
                            "hasRecordArrays",
                            !recordArrayElements.isEmpty()),
                    out);
        }

        // Generate per-module src/<module>.rs
        for (var module : proxy.modules) {
            if (module.name.names.get(0).equals(Name.fromLower("gnatpolyglot"))) continue;

            Path moduleFile = srcDir.resolve(module.name.getLastName().toLower() + ".rs");
            try (FileOutput out = new FileOutput(moduleFile)) {
                templateEngine.render("module.jte", Map.of("api", api, "module", module), out);
            }
        }

        // Generate src/arrays.rs with the PolyglotArrayElement impls for record element types.
        if (!recordArrayElements.isEmpty()) {
            Path arraysFile = srcDir.resolve("arrays.rs");
            try (FileOutput out = new FileOutput(arraysFile)) {
                templateEngine.render(
                        "arrays.jte", Map.of("api", api, "elements", recordArrayElements), out);
            }
        }
    }
}

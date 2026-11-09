//
//  Copyright (C) 2026, AdaCore
//  SPDX-License-Identifier: GPL-3.0-or-later
//

package com.adacore.gnatpolyglot.proxy2rust;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.adacore.gnatpolyglot.NativeType;
import com.adacore.gnatpolyglot.proxy.FullyQualifiedName;
import com.adacore.gnatpolyglot.proxy.FunctionDecl;
import com.adacore.gnatpolyglot.proxy.FunctionTypeExpr;
import com.adacore.gnatpolyglot.proxy.Module;
import com.adacore.gnatpolyglot.proxy.Name;
import com.adacore.gnatpolyglot.proxy.Owner;
import com.adacore.gnatpolyglot.proxy.Parameter;
import com.adacore.gnatpolyglot.proxy.Proxy;
import com.adacore.gnatpolyglot.proxy.Transfer;
import com.adacore.gnatpolyglot.proxy.TypeExpr;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class RustPrinterTest {
    @TempDir Path temporary;

    private Path proxy(TypeExpr result, TypeExpr... parameters) throws Exception {
        var args = new java.util.ArrayList<Parameter>();
        for (int i = 0; i < parameters.length; i++) {
            args.add(
                    new Parameter(
                            Name.fromLower("arg_" + i),
                            parameters[i],
                            new Transfer(Transfer.RequiredOwner.ANY)));
        }
        var function =
                new FunctionDecl(
                        new FullyQualifiedName(Name.fromLower("probe"), Name.fromLower("call")),
                        "",
                        null,
                        "probe_call",
                        new FunctionTypeExpr(args, result, Owner.UNKNOWN),
                        null,
                        null,
                        null);
        var proxy =
                new Proxy(
                        Name.fromLower("probe_bindings"),
                        "ada",
                        List.of(
                                new Module(
                                        new FullyQualifiedName(Name.fromLower("probe")),
                                        List.of(function))));
        Path file = temporary.resolve("proxy.json");
        proxy.writeProxy(file.toFile());
        return file;
    }

    @Test
    void runtimePathsCanMixRelativeAndAbsoluteForms() throws Exception {
        Path input = proxy(NativeType.SINT32.typeExpr);
        Path output = temporary.resolve("generated with spaces");
        Assumptions.assumeTrue(Path.of("").toAbsolutePath().getRoot().equals(output.getRoot()));
        Path relative = Path.of("").toAbsolutePath().relativize(output);
        Path runtime = temporary.resolve("runtime with spaces");
        new RustPrinter(input).generate(relative, runtime);
        String cargo = Files.readString(output.resolve("Cargo.toml"));
        assertTrue(cargo.contains("../runtime with spaces/ada/src2rust"));
        assertFalse(cargo.contains("\\\\"));
    }
}

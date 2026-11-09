//
//  Copyright (C) 2026, AdaCore
//  SPDX-License-Identifier: GPL-3.0-or-later
//

package com.adacore.gnatpolyglot.proxy2rust;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.adacore.gnatpolyglot.NativeType;
import com.adacore.gnatpolyglot.proxy.EnumItem;
import com.adacore.gnatpolyglot.proxy.EnumerationDecl;
import com.adacore.gnatpolyglot.proxy.FullyQualifiedName;
import com.adacore.gnatpolyglot.proxy.FunctionDecl;
import com.adacore.gnatpolyglot.proxy.FunctionTypeExpr;
import com.adacore.gnatpolyglot.proxy.Module;
import com.adacore.gnatpolyglot.proxy.Name;
import com.adacore.gnatpolyglot.proxy.Owner;
import com.adacore.gnatpolyglot.proxy.Parameter;
import com.adacore.gnatpolyglot.proxy.Proxy;
import com.adacore.gnatpolyglot.proxy.ProxyException;
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
    void embeddedScalarsNeedNoRuntime() throws Exception {
        Path input =
                proxy(
                        NativeType.SINT32.typeExpr,
                        NativeType.SINT32.typeExpr.makeReference(false),
                        NativeType.FLOAT32.typeExpr);
        Path output = temporary.resolve("embedded");
        new RustPrinter(input, true).generate(output, null);
        assertTrue(Files.readString(output.resolve("src/lib.rs")).contains("#![no_std]"));
        assertFalse(
                Files.readString(output.resolve("Cargo.toml")).contains("gnatpolyglot_runtime"));
        String build = Files.readString(output.resolve("build.rs"));
        assertFalse(build.contains("rustc-link-lib=dl"));
        assertFalse(build.contains("rustc-link-lib=advapi32"));
        assertFalse(build.contains("libgnat.a"));
        assertTrue(Files.readString(output.resolve("src/probe.rs")).contains("&mut i32"));
    }

    @Test
    void embeddedRejectsRuntimeTypesAndReturnedReferences() throws Exception {
        for (TypeExpr type :
                List.of(
                        NativeType.STRING.typeExpr,
                        NativeType.SINT32.typeExpr.makeArray(),
                        NativeType.SINT32.typeExpr.makePointer(true, true),
                        NativeType.SINT32.typeExpr.makeReference(true),
                        NativeType.SINT128.typeExpr)) {
            Path input = proxy(type);
            ProxyException error =
                    assertThrows(ProxyException.class, () -> new RustPrinter(input, true));
            assertTrue(error.getMessage().contains("--embedded:"));
        }
    }

    @Test
    void embeddedRejectsRuntimeParameters() throws Exception {
        for (TypeExpr type :
                List.of(
                        NativeType.STRING.typeExpr,
                        NativeType.SINT32.typeExpr.makeArray(),
                        NativeType.SINT32.typeExpr.makePointer(false, true),
                        NativeType.FLOAT128.typeExpr)) {
            Path input = proxy(NativeType.VOID.typeExpr, type);
            ProxyException error =
                    assertThrows(ProxyException.class, () -> new RustPrinter(input, true));
            assertTrue(error.getMessage().contains("--embedded:"));
        }
    }

    @Test
    void embeddedRejectsUserTypeDeclarations() throws Exception {
        Path input = proxy(NativeType.SINT32.typeExpr);
        Proxy original = Proxy.readProxy(input.toFile());
        var module = original.modules.getFirst();
        var enumeration =
                new EnumerationDecl(
                        new FullyQualifiedName(Name.fromLower("probe"), Name.fromLower("state")),
                        "",
                        List.of(
                                new EnumItem(Name.fromLower("first"), 0, ""),
                                new EnumItem(Name.fromLower("second"), 1, "")));
        new Proxy(
                        original.name,
                        original.inputLanguage,
                        List.of(
                                new Module(
                                        module.name,
                                        List.of(enumeration, module.declarations.getFirst()))))
                .writeProxy(input.toFile());
        ProxyException error =
                assertThrows(ProxyException.class, () -> new RustPrinter(input, true));
        assertTrue(error.getMessage().contains("only free scalar functions"));
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

//
//  Copyright (C) 2026, AdaCore
//  SPDX-License-Identifier: GPL-3.0-or-later
//

package com.adacore.gnatpolyglot.proxy2rust;

import com.adacore.gnatpolyglot.NativeType;
import com.adacore.gnatpolyglot.NativeType.NativeTypeDecl;
import com.adacore.gnatpolyglot.proxy.FunctionDecl;
import com.adacore.gnatpolyglot.proxy.NameTypeExpr;
import com.adacore.gnatpolyglot.proxy.Proxy;
import com.adacore.gnatpolyglot.proxy.ProxyContext;
import com.adacore.gnatpolyglot.proxy.ProxyException;
import com.adacore.gnatpolyglot.proxy.ReferenceTypeExpr;
import com.adacore.gnatpolyglot.proxy.Transfer.RequiredOwner;
import com.adacore.gnatpolyglot.proxy.TypeExpr;

/** The initial embedded profile deliberately needs neither allocation nor the Ada proxy runtime. */
final class EmbeddedProfile {
    private EmbeddedProfile() {}

    static void validate(Proxy proxy, ProxyContext context) throws ProxyException {
        RustAPI api = new RustAPI(context, proxy.name);
        for (var module : proxy.modules) {
            if (api.isGnatpolyglotModule(module)) continue;
            for (var declaration : module.declarations) {
                String name = declaration.name.toString();
                if (!(declaration instanceof FunctionDecl function) || function.role != null) {
                    throw unsupported(name, "only free scalar functions are supported");
                }
                scalar(context, function.type.returnType, true, name);
                for (var parameter : function.type.parameters) {
                    TypeExpr type = parameter.type;
                    if (type instanceof ReferenceTypeExpr reference)
                        type = reference.referencedType();
                    scalar(context, type, false, name + " parameter " + parameter.name);
                    if (parameter.transfer.required_owner != RequiredOwner.ANY) {
                        throw unsupported(name, "ownership transfer is unsupported");
                    }
                }
            }
        }
    }

    private static void scalar(ProxyContext context, TypeExpr type, boolean allowVoid, String name)
            throws ProxyException {
        if (type instanceof NameTypeExpr named
                && context.getTypeDecl(named.name) instanceof NativeTypeDecl nativeType) {
            NativeType kind = nativeType.nativeType;
            switch (kind) {
                case BOOL,
                        CHAR,
                        SINT8,
                        UINT8,
                        SINT16,
                        UINT16,
                        SINT32,
                        UINT32,
                        SINT64,
                        UINT64,
                        FLOAT32,
                        FLOAT64 -> {
                    return;
                }
                case VOID -> {
                    if (allowVoid) return;
                }
                default -> {}
            }
        }
        throw unsupported(name, "expected a fixed-width scalar" + (allowVoid ? " or void" : ""));
    }

    private static ProxyException unsupported(String name, String reason) {
        return new ProxyException("--embedded: " + name + ": " + reason);
    }
}

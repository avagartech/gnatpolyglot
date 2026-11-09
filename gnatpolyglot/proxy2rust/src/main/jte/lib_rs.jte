<%--
Copyright (C) 2025-2026, AdaCore
SPDX-License-Identifier: GPL-3.0-or-later
Template file to generate the root lib.rs for a Rust binding crate.
--%>
@import com.adacore.gnatpolyglot.proxy.Proxy
@import com.adacore.gnatpolyglot.proxy2rust.RustAPI

@param RustAPI api
@param Proxy proxy
@param boolean hasRecordArrays
@param boolean embedded

!{
    var userModules = proxy.modules.stream()
            .filter(m -> !api.isGnatpolyglotModule(m))
            .toList();
}

@if (embedded)
#![no_std]
@else
// Re-export the runtime support module tree (ada::arrays, ada::strings, ...) so downstream code
// can name those types through this crate without taking a direct dependency on the runtime
// crate. The module path is preserved (not flattened), mirroring the C++ gnatpolyglot::ada::*
// namespaces: a `use <crate>::ada::arrays::PolyglotArray;` then needs no further mention of Ada.
pub use gnatpolyglot_runtime::ada;
@endif

@for (var module : userModules)
pub mod ${api.rustModuleName(module)};
@endfor
@if (hasRecordArrays)
// PolyglotArrayElement impls for record element types (see arrays.rs).
mod arrays;
@endif

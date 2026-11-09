<%--
Copyright (C) 2025-2026, AdaCore
SPDX-License-Identifier: GPL-3.0-or-later
Template file to generate build.rs for a Rust binding crate.
Links against the proxy library via POLYGLOT_PROXY_LIB_DIR / POLYGLOT_PROXY_LIB_NAME.
--%>
@import com.adacore.gnatpolyglot.proxy.Proxy
@import com.adacore.gnatpolyglot.proxy2rust.RustAPI

@param RustAPI api
@param Proxy proxy
@param boolean embedded

fn main() {
    println!("cargo:rerun-if-env-changed=POLYGLOT_PROXY_LIB_DIR");
    println!("cargo:rerun-if-env-changed=POLYGLOT_PROXY_LIB_NAME");
    if let Ok(dir) = std::env::var("POLYGLOT_PROXY_LIB_DIR") {
        println!("cargo:rustc-link-search=native={}", dir);
    }
    if let Ok(name) = std::env::var("POLYGLOT_PROXY_LIB_NAME") {
        println!("cargo:rustc-link-lib=static={}", name);
        if let Ok(dir) = std::env::var("POLYGLOT_PROXY_LIB_DIR") {
            let archive = std::path::Path::new(&dir).join(format!("lib{}.a", name));
            println!("cargo:rerun-if-changed={}", archive.display());
        }
    }
@if (!embedded)
    // Build scripts run on the host, so cfg!(target_os) would select the
    // host's libraries even when Cargo is building for a different target.
    match std::env::var("CARGO_CFG_TARGET_OS").as_deref() {
        Ok("linux") => {
            println!("cargo:rustc-link-lib=dl");
            println!("cargo:rustc-link-lib=pthread");
        }
        Ok("windows") => {
            // The GNAT runtime uses Win32 security, ACL and registry APIs.
            println!("cargo:rustc-link-lib=advapi32");
        }
        _ => {}
    }
@endif
}

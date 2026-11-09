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
    println!("cargo:rerun-if-env-changed=POLYGLOT_ADA_COMPILER");
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
        Ok("macos") => {
            // libSystem provides dlopen and pthreads and is linked by rustc.
            // Darwin GNAT toolchains may require a standard standalone
            // library instead of an encapsulated one. Bundle its runtime
            // archives into this crate so dependent binaries can link them.
            if let Ok(compiler) = std::env::var("POLYGLOT_ADA_COMPILER") {
                for (file, name, required) in [
                    ("adalib/libgnarl.a", "gnarl", true),
                    ("adalib/libgnat.a", "gnat", true),
                    ("libemutls_w.a", "emutls_w", false),
                ] {
                    let output = std::process::Command::new(&compiler)
                        .arg(format!("-print-file-name={}", file))
                        .output()
                        .expect("cannot run POLYGLOT_ADA_COMPILER (use the target GNAT gcc)");
                    assert!(output.status.success(), "POLYGLOT_ADA_COMPILER query failed");
                    let path = String::from_utf8(output.stdout).expect("invalid compiler output");
                    let path = std::path::Path::new(path.trim());
                    if path.is_file() {
                        println!("cargo:rustc-link-search=native={}", path.parent().unwrap().display());
                        println!("cargo:rustc-link-lib=static={}", name);
                        println!("cargo:rerun-if-changed={}", path.display());
                    } else {
                        assert!(!required, "cannot find {} using POLYGLOT_ADA_COMPILER", file);
                    }
                }
            }
        }
        _ => {}
    }
@endif
}

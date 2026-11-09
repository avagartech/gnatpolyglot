<%--
Copyright (C) 2025-2026, AdaCore
SPDX-License-Identifier: GPL-3.0-or-later
Template file to generate the Cargo.toml for a Rust binding crate.
--%>
@import com.adacore.gnatpolyglot.proxy.Proxy
@import com.adacore.gnatpolyglot.proxy2rust.RustAPI

@param RustAPI api
@param Proxy proxy
@param String runtimeLocation

[package]
name = "${proxy.name.toLower()}"
version = "0.1.0"
edition = "2021"

[dependencies]
gnatpolyglot_runtime = { path = ${runtimeLocation} }

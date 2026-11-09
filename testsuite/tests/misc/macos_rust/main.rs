// Copyright (C) 2026, AdaCore
// SPDX-License-Identifier: GPL-3.0-or-later

use macos_smoke::ada::arrays::PolyglotArray;
use macos_smoke::ada::strings::PolyglotString;
use macos_smoke::smoke;

fn main() {
    assert_eq!(smoke::add(19, 23), 42);
    assert_eq!(smoke::initial_value(), 42, "Ada elaboration must run automatically");
    {
        let mut ints = PolyglotArray::<i32>::new(-2, 2);
        ints.set(-2, 42);
        assert_eq!(ints.get(-2), Some(42));
        assert_eq!(ints.get(-3), None);
        let mut doubles = PolyglotArray::<f64>::new(1, 2);
        doubles.set(1, 3.5);
        assert_eq!(doubles.get(1), Some(3.5));
        let text = PolyglotString::from("Ada → Rust on macOS");
        assert_eq!(text.to_string(), "Ada → Rust on macOS");
    }
    println!("macOS Ada/Rust smoke passed");
}

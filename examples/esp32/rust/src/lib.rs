// Copyright (C) 2026, AdaCore
// SPDX-License-Identifier: GPL-3.0-or-later

#![no_std]

use esp32_bindings::abi_probe;

#[cfg(feature = "firmware")]
extern "C" {
    fn polyglot_esp32_abort() -> !;
}

#[cfg(feature = "firmware")]
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    unsafe { polyglot_esp32_abort() }
}

/// Zero means all ABI and error-status checks passed; each set bit identifies a failure.
#[no_mangle]
pub extern "C" fn polyglot_esp32_self_test() -> u32 {
    let mut failures = 0;
    let mut total = 0;
    if abi_probe::checked_add(19, 23, &mut total) != 0 || total != 42 {
        failures |= 1;
    }
    total = 99;
    if abi_probe::checked_add(i32::MAX, 1, &mut total) != 1 || total != 99 {
        failures |= 2;
    }
    if abi_probe::checked_add(i32::MIN, -1, &mut total) != 1 || total != 99 {
        failures |= 4;
    }
    if abi_probe::fold_64(0xFEDC_BA98_7654_3210) != 0xEFFE_89DC_2332_4598 {
        failures |= 8;
    }
    if abi_probe::scale_32(2.5) != 3.75 {
        failures |= 16;
    }
    if abi_probe::scale_64(2.5) != 3.75 {
        failures |= 32;
    }
    if abi_probe::negate_16(-12345) != 12345
        || abi_probe::negate_16(i16::MIN) != i16::MIN
    {
        failures |= 64;
    }
    failures
}

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>

/* Stable debugger-visible result: magic, build chip ID, state, failure mask. */
struct Probe_Result {
    uint32_t magic;
    uint32_t chip;
    uint32_t state;
    uint32_t failures;
};
volatile struct Probe_Result polyglot_stm32_result;
static volatile uint32_t data_cookie = 0x13579bdf;
static volatile uint32_t bss_cookie;

enum { RUNNING = 1, PASS = 2, FAIL = 3, ADA_CHECK = 4, RUST_PANIC = 5, FAULT = 6 };
extern uint32_t polyglot_stm32_self_test(void);

__attribute__((noreturn, noinline)) void polyglot_stm32_done(void) {
    __asm__ volatile ("dsb" ::: "memory");
    for (;;) {
        __asm__ volatile ("wfi");
    }
}

__attribute__((noreturn)) static void stop(uint32_t state, uint32_t failures) {
    polyglot_stm32_result.magic = 0x47504c54;
    polyglot_stm32_result.chip = POLYGLOT_CHIP_ID;
    polyglot_stm32_result.failures = failures;
    polyglot_stm32_result.state = state;
    polyglot_stm32_done();
}

__attribute__((noreturn)) void __gnat_last_chance_handler(const char *file, int line) {
    (void)file;
    (void)line;
    stop(ADA_CHECK, UINT32_MAX);
}

__attribute__((noreturn)) void polyglot_stm32_abort(void) {
    stop(RUST_PANIC, UINT32_MAX);
}

__attribute__((noreturn)) void polyglot_stm32_fault(void) {
    stop(FAULT, UINT32_MAX);
}

__attribute__((noreturn)) void polyglot_stm32_main(void) {
    polyglot_stm32_result.magic = 0x47504c54;
    polyglot_stm32_result.chip = POLYGLOT_CHIP_ID;
    polyglot_stm32_result.state = RUNNING;
    uint32_t core = (*(volatile uint32_t *)0xe000ed00 >> 4) & 0xfff;
    if (core != POLYGLOT_CPUID_PART) {
        stop(FAIL, 0x80000000);
    }
    if (data_cookie != 0x13579bdf || bss_cookie != 0) {
        stop(FAIL, 0x40000000);
    }
    uint32_t failures = polyglot_stm32_self_test();
    stop(failures == 0 ? PASS : FAIL, failures);
}

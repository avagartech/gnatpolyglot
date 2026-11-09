// Copyright (C) 2026, AdaCore
// SPDX-License-Identifier: GPL-3.0-or-later

#include <Arduino.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern "C" uint32_t polyglot_esp32_self_test();

extern "C" void __gnat_last_chance_handler(const char*, int) {
    Serial.println("GNATPOLYGLOT FAIL: Ada runtime check");
    Serial.flush();
    abort();
}

extern "C" void polyglot_esp32_abort() {
    Serial.println("GNATPOLYGLOT FAIL: Rust panic");
    Serial.flush();
    abort();
}

static void test() {
    uint32_t failures = polyglot_esp32_self_test();
    Serial.printf("GNATPOLYGLOT %s mask=0x%08lx\n",
                  failures == 0 ? "PASS" : "FAIL", (unsigned long)failures);
    Serial.flush();
}

void setup() {
    Serial.begin(115200);
    delay(250);
    Serial.println("GNATPOLYGLOT ESP32-WROOM READY");
    test();
}

void loop() {
    static char command[16];
    static size_t used = 0;
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            command[used] = '\0';
            if (strcmp(command, "TEST") == 0) test();
            used = 0;
        } else if (c != '\r' && used + 1 < sizeof(command)) {
            command[used++] = c;
        }
    }
    delay(1);
}

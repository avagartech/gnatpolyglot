/* SPDX-License-Identifier: GPL-3.0-or-later */
.syntax unified
.thumb

.section .isr_vector,"a",%progbits
.balign 1024
.global polyglot_vectors
polyglot_vectors:
    .word _stack_top
    .word Reset_Handler
    /* All remaining core exceptions and the maximum 240 external IRQs trap. */
    .rept 254
    .word Default_Handler
    .endr

.section .text.Reset_Handler,"ax",%progbits
.global Reset_Handler
.type Reset_Handler,%function
.thumb_func
Reset_Handler:
    cpsid i
    /* Enable CP10/CP11 before any hard-float Ada, Rust, or C code runs. */
    ldr r0, =0xe000ed88
    ldr r1, [r0]
    orr r1, r1, #0x00f00000
    str r1, [r0]
    dsb
    isb
    ldr r0, =0xe000ed08
    ldr r1, =polyglot_vectors
    str r1, [r0]
    dsb
    isb
    ldr r0, =_sidata
    ldr r1, =_sdata
    ldr r2, =_edata
1:  cmp r1, r2
    bcs 2f
    ldr r3, [r0], #4
    str r3, [r1], #4
    b 1b
2:  ldr r1, =_sbss
    ldr r2, =_ebss
    movs r3, #0
3:  cmp r1, r2
    bcs 4f
    str r3, [r1], #4
    b 3b
4:  bl polyglot_stm32_main
    b Default_Handler
.size Reset_Handler, .-Reset_Handler

.section .text.Default_Handler,"ax",%progbits
.global Default_Handler
.type Default_Handler,%function
.thumb_func
Default_Handler:
    b polyglot_stm32_fault
.size Default_Handler, .-Default_Handler

.section .note.GNU-stack,"",%progbits

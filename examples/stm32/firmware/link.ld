/* SPDX-License-Identifier: GPL-3.0-or-later */
INCLUDE memory.ld
ENTRY(Reset_Handler)
_stack_top = ORIGIN(RAM) + LENGTH(RAM);
_stack_limit = _stack_top - 4096;

SECTIONS
{
    .isr_vector ORIGIN(FLASH) : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .ARM.extab : { *(.ARM.extab*) } > FLASH
    .ARM.exidx : {
        __exidx_start = .;
        *(.ARM.exidx*)
        __exidx_end = .;
    } > FLASH
    .unexpected_init : {
        *(.preinit_array* .init_array* .fini_array* .init .fini .ctors* .dtors*)
    } > FLASH
    .data : {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4);
        _sbss = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM
    .ARM.attributes 0 : { *(.ARM.attributes) }
    /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(SIZEOF(.unexpected_init) == 0, "This probe does not run static constructors")
ASSERT(_ebss <= _stack_limit, "Static data overlaps the reserved 4 KiB stack")

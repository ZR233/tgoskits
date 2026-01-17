/* 
 * Test linker script that works for both architectures
 * The actual OUTPUT_ARCH will be determined by the target
 */

STACK_SIZE = 0x40000;

INCLUDE "someboot.x"

SECTIONS
{
   .driver : ALIGN(4K) {
        _sdriver = .;
        KEEP(*(.driver.register))
        _edriver = .;
    }
} INSERT AFTER .data;

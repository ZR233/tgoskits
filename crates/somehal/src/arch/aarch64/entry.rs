use core::arch::{asm, naked_asm};

use super::switch_to_elx;

#[unsafe(naked)]
#[unsafe(no_mangle)]
pub unsafe extern "C" fn kernel_entry(_fdt_addr: usize) -> ! {
    naked_asm!(
        "mov  x9,  x0",

        // Clear BSS section from __bss_start to __bss_stop
        asm_sym_addr!(x0, "__bss_start"),
        asm_sym_addr!(x1, "__bss_stop"),
        "mov x2, #0",        // Zero value to store
        "1:",
        "cmp x0, x1",        // Compare current address with end
        "b.eq 2f",           // If reached end, exit loop
        "str x2, [x0], #8",  // Store zero and advance by 8 bytes
        "b 1b",              // Loop back
        "2:",

        asm_sym_addr!(x8, "{fdt}"),
        "str  x9, [x8]",

        asm_sym_addr!(x8, "__cpu0_stack_top"),
        "mov sp, x8",

        "bl {switch_to_elx}",
        fdt = sym crate::fdt::FDT_ADDR,
        switch_to_elx = sym switch_to_elx,
    )
}

pub fn el_entry() -> ! {
    super::relocate::apply();
    super::trap::setup();

    crate::fdt::setup_earlycon();
    if let Some(cmdline) = crate::cmdline::cmdline() {
        println!("{cmdline}");
    }

    crate::mem::early_init();
    crate::arch::paging::enable_mmu()
    // crate::fdt::setup_memory_map();

    // println!("Hello, Somehal on AArch64!");

    // loop {}
}

pub fn mmu_entry() -> ! {
    // Immediate check if we got here
    println!("=== MMU_ENTRY REACHED ===");

    // Check MMU status
    println!("MMU status in mmu_entry: {:#x}", {
        let mut sctlr: u64;
        unsafe { asm!("mrs {}, sctlr_el1", out(reg) sctlr); }
        sctlr
    });

    // Check current exception level
    println!("Current EL: {}", {
        let mut el: u64;
        unsafe { asm!("mrs {}, currentel", out(reg) el); }
        (el >> 2) & 0x3
    });

    // Check TTBR0/TTBR1
    println!("TTBR0_EL1: {:#x}", {
        let mut ttbr0: u64;
        unsafe { asm!("mrs {}, ttbr0_el1", out(reg) ttbr0); }
        ttbr0
    });

    println!("TTBR1_EL1: {:#x}", {
        let mut ttbr1: u64;
        unsafe { asm!("mrs {}, ttbr1_el1", out(reg) ttbr1); }
        ttbr1
    });

    // Check TCR
    println!("TCR_EL1: {:#x}", {
        let mut tcr: u64;
        unsafe { asm!("mrs {}, tcr_el1", out(reg) tcr); }
        tcr
    });

    println!("MMU is enabled and working!");

    // Try to access some memory
    let test_addr = 0x40200000 as *mut u64;
    println!("Testing memory access at {:#x}", test_addr as usize);

    unsafe {
        let val = test_addr.read_volatile();
        println!("Read value: {:#x}", val);
    }

    println!("All tests passed!");

    loop {}
}

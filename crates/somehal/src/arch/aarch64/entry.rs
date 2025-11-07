use core::arch::naked_asm;

use super::switch_to_elx;

#[unsafe(naked)]
pub unsafe extern "C" fn primary_entry(_fdt_addr: usize) -> ! {
    naked_asm!(
        sym_addr!(x8, "{fdt}"),
        "str  x0, [x8]",

        sym_addr!(x8, "__cpu0_stack_top"),
        "mov sp, x9",

        "bl {switch_to_elx}",
        fdt = sym crate::fdt::FDT_ADDR,
        switch_to_elx = sym switch_to_elx,
    )
}

pub fn el_entry() -> !{
    


    loop{}    
}
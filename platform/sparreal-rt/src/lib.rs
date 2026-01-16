#![no_std]
#![no_main]
#![cfg(not(any(windows, unix)))]

extern crate alloc;
extern crate someplat;

use someplat::KernelOp;
pub use sparreal_kernel::entry;
pub use sparreal_kernel::*;

mod hal_impl;

#[someboot::entry]
fn main() -> ! {
    someplat::set_kernel_op(&Kernel);
    sparreal_kernel::run_kernel()
}

pub struct Kernel;

impl KernelOp for Kernel {
    fn ioremap(&self, paddr: usize, size: usize) -> someboot::PagingResult<*mut u8> {
        sparreal_kernel::os::mem::ioremap(paddr.into(), size).map(|addr| addr.raw() as *mut u8)
    }
}

#![no_std]
#![no_main]
#![cfg(not(any(windows, unix)))]

#[macro_use]
extern crate alloc;

pub use page_table_generic::{PagingError, PagingResult};
use rdrive::probe::OnProbeError;
pub use someboot::*;

#[cfg(target_arch = "loongarch64")]
#[path = "arch/loongarch64/mod.rs"]
pub mod arch;

#[cfg(target_arch = "aarch64")]
#[path = "arch/aarch64/mod.rs"]
pub mod arch;

pub trait PlatOp {}

pub trait KernelOp {
    fn ioremap(&self, paddr: usize, size: usize) -> PagingResult<*mut u8>;
}

struct EmptyKernelOp;

impl KernelOp for EmptyKernelOp {
    fn ioremap(&self, _paddr: usize, _size: usize) -> PagingResult<*mut u8> {
        unimplemented!()
    }
}

static mut KERNEL_OP: &'static dyn KernelOp = &EmptyKernelOp;

pub fn set_kernel_op(op: &'static dyn KernelOp) {
    unsafe {
        KERNEL_OP = op;
    }
}

fn kernel() -> &'static dyn KernelOp {
    unsafe { KERNEL_OP }
}

fn ioremap(paddr: usize, size: usize) -> Result<*mut u8, IoremapError> {
    let ptr = kernel().ioremap(paddr, size)?;
    Ok(ptr)
}

#[derive(thiserror::Error, Debug)]
#[error(transparent)]
struct IoremapError(#[from] PagingError);

impl From<IoremapError> for OnProbeError {
    fn from(value: IoremapError) -> Self {
        OnProbeError::Other(format!("ioremap error: {value}").into())
    }
}

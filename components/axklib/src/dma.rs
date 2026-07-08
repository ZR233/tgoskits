use core::{alloc::Layout, num::NonZeroUsize, ptr::NonNull};

use ax_memory_addr::{MemoryAddr, PAGE_SIZE_4K, VirtAddr};
use dma_api::{
    DeviceDma, DmaAllocHandle, DmaConstraints, DmaDirection, DmaDomainId, DmaError, DmaMapHandle,
    DmaOp,
};

pub struct KlibDma;

static DMA: KlibDma = KlibDma;

pub fn op() -> &'static KlibDma {
    &DMA
}

pub const fn domain_id() -> DmaDomainId {
    DmaDomainId::legacy_global()
}

pub fn device_with_mask(dma_mask: u64) -> DeviceDma {
    DeviceDma::new(domain_id(), dma_mask, op())
}

struct DmaPages {
    cpu_addr: NonNull<u8>,
    dma_addr: u64,
    num_pages: usize,
}

impl DmaPages {
    fn layout_pages(layout: Layout) -> usize {
        layout.size().div_ceil(PAGE_SIZE_4K)
    }

    fn layout_align(layout: Layout, constraints: DmaConstraints) -> usize {
        layout.align().max(constraints.align).max(PAGE_SIZE_4K)
    }

    /// Allocates DMA-visible pages using the kernel DMA allocator.
    ///
    /// `dma_alloc_pages` is expected to honor `addr_mask` and the requested
    /// alignment. The checks below are defensive validation so a bad platform
    /// allocator fails before the buffer is handed to a device.
    unsafe fn alloc_for_layout(
        constraints: DmaConstraints,
        layout: Layout,
    ) -> Result<Self, DmaError> {
        if layout.size() == 0 {
            return Ok(Self {
                cpu_addr: NonNull::dangling(),
                dma_addr: 0,
                num_pages: 0,
            });
        }

        let num_pages = Self::layout_pages(layout);
        let align = Self::layout_align(layout, constraints);
        let cpu_vaddr = crate::klib::dma_alloc_pages(constraints.addr_mask, num_pages, align)
            .map_err(|_| DmaError::NoMemory)?;
        let cpu_addr = NonNull::new(cpu_vaddr.as_mut_ptr()).ok_or(DmaError::NoMemory)?;
        let dma_addr = dma_addr_from_vaddr(cpu_vaddr);

        if !dma_range_fits_mask(dma_addr, layout.size(), constraints.addr_mask) {
            unsafe { Self::dealloc_pages(cpu_addr, num_pages) };
            return Err(DmaError::DmaMaskNotMatch {
                addr: dma_addr.into(),
                mask: constraints.addr_mask,
            });
        }
        if !dma_addr_is_aligned(dma_addr, constraints.align.max(layout.align())) {
            unsafe { Self::dealloc_pages(cpu_addr, num_pages) };
            return Err(DmaError::AlignMismatch {
                required: constraints.align.max(layout.align()),
                address: dma_addr.into(),
            });
        }

        Ok(Self {
            cpu_addr,
            dma_addr,
            num_pages,
        })
    }

    unsafe fn dealloc_pages(cpu_addr: NonNull<u8>, num_pages: usize) {
        if num_pages == 0 {
            return;
        }
        crate::klib::dma_dealloc_pages(VirtAddr::from_usize(cpu_addr.as_ptr() as usize), num_pages);
    }
}

struct CoherentDmaPolicy;

impl CoherentDmaPolicy {
    fn make_uncached(pages: &DmaPages, layout: Layout) -> Result<(), DmaError> {
        if pages.num_pages == 0 {
            return Ok(());
        }

        let range_size = pages.num_pages * PAGE_SIZE_4K;
        let start = VirtAddr::from_usize(pages.cpu_addr.as_ptr() as usize).align_down_4k();
        crate::klib::mem_make_dma_coherent_uncached(start, range_size)
            .map_err(|_| DmaError::NoMemory)?;
        unsafe {
            pages.cpu_addr.as_ptr().write_bytes(0, layout.size());
        }
        Ok(())
    }

    fn restore_cached(pages: NonNull<u8>, num_pages: usize) -> Result<(), DmaError> {
        if num_pages == 0 {
            return Ok(());
        }

        let start = VirtAddr::from_usize(pages.as_ptr() as usize).align_down_4k();
        crate::klib::mem_restore_dma_cached(start, num_pages * PAGE_SIZE_4K)
            .map_err(|_| DmaError::NoMemory)
    }
}

impl DmaOp for KlibDma {
    fn page_size(&self) -> usize {
        PAGE_SIZE_4K
    }

    unsafe fn alloc_contiguous(
        &self,
        constraints: DmaConstraints,
        layout: Layout,
    ) -> Option<DmaAllocHandle> {
        let pages = unsafe { DmaPages::alloc_for_layout(constraints, layout).ok()? };
        Some(unsafe { DmaAllocHandle::new(pages.cpu_addr, pages.dma_addr.into(), layout) })
    }

    unsafe fn dealloc_contiguous(&self, handle: DmaAllocHandle) {
        let num_pages = DmaPages::layout_pages(handle.layout());
        unsafe { DmaPages::dealloc_pages(handle.as_ptr(), num_pages) };
    }

    unsafe fn alloc_coherent(
        &self,
        constraints: DmaConstraints,
        layout: Layout,
    ) -> Option<DmaAllocHandle> {
        let pages = unsafe { DmaPages::alloc_for_layout(constraints, layout).ok()? };
        if CoherentDmaPolicy::make_uncached(&pages, layout).is_err() {
            unsafe { DmaPages::dealloc_pages(pages.cpu_addr, pages.num_pages) };
            return None;
        }

        Some(unsafe { DmaAllocHandle::new(pages.cpu_addr, pages.dma_addr.into(), layout) })
    }

    unsafe fn dealloc_coherent(&self, handle: DmaAllocHandle) {
        let num_pages = DmaPages::layout_pages(handle.layout());
        if CoherentDmaPolicy::restore_cached(handle.as_ptr(), num_pages).is_err() {
            return;
        }
        unsafe { DmaPages::dealloc_pages(handle.as_ptr(), num_pages) };
    }

    unsafe fn map_streaming(
        &self,
        constraints: DmaConstraints,
        addr: NonNull<u8>,
        size: NonZeroUsize,
        _direction: DmaDirection,
    ) -> Result<DmaMapHandle, DmaError> {
        let align = constraints.align.max(1);
        let layout = Layout::from_size_align(size.get(), align)?;
        let dma_addr = dma_addr_from_ptr(addr);

        if dma_range_fits_mask(dma_addr, size.get(), constraints.addr_mask)
            && dma_addr_is_aligned(dma_addr, align)
        {
            return Ok(unsafe { DmaMapHandle::new(addr, dma_addr.into(), layout, None) });
        }

        let map_pages = unsafe { DmaPages::alloc_for_layout(constraints, layout)? };
        Ok(unsafe {
            DmaMapHandle::new(
                addr,
                map_pages.dma_addr.into(),
                layout,
                Some(map_pages.cpu_addr),
            )
        })
    }

    unsafe fn unmap_streaming(&self, handle: DmaMapHandle) {
        if let Some(map_virt) = handle.bounce_ptr() {
            let num_pages = DmaPages::layout_pages(handle.layout());
            unsafe { DmaPages::dealloc_pages(map_virt, num_pages) };
        }
    }

    #[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
    fn flush(&self, addr: NonNull<u8>, size: usize) {
        thead_dma_fence();
        thead_dma_wb_range(dma_addr_from_ptr(addr), size);
    }

    #[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
    fn invalidate(&self, addr: NonNull<u8>, size: usize) {
        thead_dma_wbinv_range(dma_addr_from_ptr(addr), size);
        thead_dma_fence();
    }

    #[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
    fn flush_invalidate(&self, addr: NonNull<u8>, size: usize) {
        thead_dma_fence();
        thead_dma_wbinv_range(dma_addr_from_ptr(addr), size);
        thead_dma_fence();
    }
}

#[cfg(any(test, all(target_arch = "riscv64", feature = "thead-cache")))]
const DMA_CACHE_LINE_SIZE: u64 = 64;

#[cfg(any(test, all(target_arch = "riscv64", feature = "thead-cache")))]
fn dma_cache_line_range(addr: u64, size: usize) -> Option<(u64, u64)> {
    if size == 0 {
        return None;
    }
    let end = addr.checked_add(size as u64)?;
    Some((addr & !(DMA_CACHE_LINE_SIZE - 1), end))
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
fn thead_dma_wb_range(addr: u64, size: usize) {
    thead_dma_cache_range(addr, size, TheadDmaCacheOp::Writeback);
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
fn thead_dma_wbinv_range(addr: u64, size: usize) {
    thead_dma_cache_range(addr, size, TheadDmaCacheOp::WritebackInvalidate);
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
#[derive(Clone, Copy)]
enum TheadDmaCacheOp {
    Writeback,
    WritebackInvalidate,
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
fn thead_dma_cache_range(addr: u64, size: usize, op: TheadDmaCacheOp) {
    let Some((mut line, end)) = dma_cache_line_range(addr, size) else {
        return;
    };

    while line < end {
        match op {
            TheadDmaCacheOp::Writeback => unsafe {
                // T-Head dcache.cpa a0: clean by physical address.
                core::arch::asm!(".long 0x0295000b", in("a0") line as usize, options(nostack));
            },
            TheadDmaCacheOp::WritebackInvalidate => unsafe {
                // T-Head dcache.cipa a0: clean and invalidate by physical address.
                core::arch::asm!(".long 0x02b5000b", in("a0") line as usize, options(nostack));
            },
        }
        line += DMA_CACHE_LINE_SIZE;
    }
    thead_sync_is();
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
fn thead_dma_fence() {
    unsafe { core::arch::asm!("fence rw, rw", options(nostack)) };
}

#[cfg(all(target_arch = "riscv64", feature = "thead-cache"))]
fn thead_sync_is() {
    unsafe { core::arch::asm!(".long 0x01b0000b", options(nostack)) };
}

fn dma_addr_from_ptr(ptr: NonNull<u8>) -> u64 {
    dma_addr_from_vaddr(VirtAddr::from_usize(ptr.as_ptr() as usize))
}

fn dma_addr_from_vaddr(vaddr: VirtAddr) -> u64 {
    crate::klib::mem_virt_to_phys(vaddr).as_usize() as u64
}

fn dma_range_fits_mask(dma_addr: u64, size: usize, dma_mask: u64) -> bool {
    if size == 0 {
        dma_addr <= dma_mask
    } else {
        dma_addr
            .checked_add(size.saturating_sub(1) as u64)
            .map(|end| end <= dma_mask)
            .unwrap_or(false)
    }
}

fn dma_addr_is_aligned(dma_addr: u64, align: usize) -> bool {
    dma_addr.is_multiple_of(align.max(1) as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dma_cache_line_range_covers_unaligned_buffer() {
        assert_eq!(dma_cache_line_range(0x1003, 1), Some((0x1000, 0x1004)));
        assert_eq!(dma_cache_line_range(0x103f, 2), Some((0x1000, 0x1041)));
    }

    #[test]
    fn dma_cache_line_range_skips_empty_and_overflow() {
        assert_eq!(dma_cache_line_range(0x1000, 0), None);
        assert_eq!(dma_cache_line_range(u64::MAX, 2), None);
    }
}

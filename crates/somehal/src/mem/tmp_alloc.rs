use core::alloc::Layout;

use buddy_system_allocator::Heap;
use num_align::NumAlign;
use page_table_generic::FrameAllocator;

use crate::ArchTrait;

use super::*;

#[derive(Clone, Copy)]
pub struct TmpAlloc;

impl FrameAllocator for TmpAlloc {
    fn alloc_frame(&self) -> Option<page_table_generic::PhysAddr> {
        let layout = Layout::from_size_align(page_size(), page_size()).ok()?;
        let res = ALLOC.update(|heap| heap.alloc(layout));
        res.map(|ptr| (ptr.as_ptr() as usize).into()).ok()
    }

    fn dealloc_frame(&self, frame: page_table_generic::PhysAddr) {
        let layout = Layout::from_size_align(page_size(), page_size()).unwrap();
        let ptr = frame.raw() as *mut u8;
        ALLOC
            .update(|heap| unsafe { heap.dealloc(core::ptr::NonNull::new_unchecked(ptr), layout) });
    }

    fn phys_to_virt(&self, paddr: page_table_generic::PhysAddr) -> *mut u8 {
        paddr.raw() as *mut u8
    }
}

static ALLOC: StaticCell<Heap<32>> = StaticCell::new(None);

pub(super) fn init() {
    let k_start = kernel_range().start;
    let k_end = kernel_range().end;
    println!(
        "Kernel at [{:#x} - {:#x}] ({} KB)",
        k_start,
        k_end,
        (k_end - k_start) / 1024
    );

    let Some(main_memory) = get_memory_map().iter().find(|m| {
        matches!(m.memory_type, MemoryType::Usable)
            && (m.physical_start..m.physical_start + m.size_in_bytes).contains(&(k_end + MB))
    }) else {
        panic!("No usable memory region found containing the kernel");
    };
    println!(
        "Main memory region: [{:#x} - {:#x}] ({} MB)",
        main_memory.physical_start,
        main_memory.physical_start + main_memory.size_in_bytes,
        main_memory.size_in_bytes / (1024 * 1024)
    );

    let free = main_memory.physical_start + main_memory.size_in_bytes - k_end;
    let start = (k_end + 8 * MB).max(k_end + free / 2).align_up(page_size());
    let size = main_memory.physical_start + main_memory.size_in_bytes - start;

    unsafe {
        let mut heap = Heap::empty();
        heap.init(start, size);
        println!(
            "TmpAlloc initialized: [{:#x} - {:#x}] ({} MB)",
            start,
            size,
            size / MB
        );
        ALLOC.set(heap);
    }
}

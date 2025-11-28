use byte_unit::{Byte, UnitType};
use kernutil::memory::MemoryDescriptor;

use crate::os::mem::address::{PhysAddr, VirtAddr};

mod address;
mod allocator;

pub fn page_size() -> usize {
    crate::hal::al::memory::page_size()
}

pub(crate) fn init_heap(regions: &[MemoryDescriptor]) {
    for region in regions {
        if region.memory_type == kernutil::memory::MemoryType::Usable {
            let start = PhysAddr::new(region.physical_start).align_up(page_size());
            let end =
                PhysAddr::new(region.physical_start + region.size_in_bytes).align_down(page_size());
            let size = end - start;
            if size == 0 {
                continue;
            }
            let byte_count = Byte::from(size);
            let adjusted_byte = byte_count.get_appropriate_unit(UnitType::Binary);
            let start: VirtAddr = start.into();
            debug!(
                "Alloc add: {} - {} ({:.2})",
                start,
                start + size,
                adjusted_byte
            );
            let memory = unsafe { core::slice::from_raw_parts_mut(start.into(), size) };

            #[cfg(target_os = "none")]
            allocator::ALLOCATOR.add_to_frame(memory);
        }
    }
}

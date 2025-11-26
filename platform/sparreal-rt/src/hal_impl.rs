use sparreal_kernel::{hal::al::*, impl_trait};

struct InitImpl;

impl_trait! {
impl Platform for InitImpl {
    fn post_allocator() {
        somehal::post_allocator();
    }
    fn shutdown() -> ! {
        somehal::power::shutdown()
    }
    fn irq_is_enabled(irq: usize) -> bool {
        todo!()
    }
    fn irq_set_enabled(irq: usize, enabled: bool) {
        todo!()
    }
}
}

struct MemoryImpl;

impl_trait! {
impl Memory for MemoryImpl {
    unsafe fn virt_to_phys(virt: *mut u8) -> usize {
        somehal::mem::virt_to_phys(virt)
    }

    fn phys_to_virt(phys: usize) -> *mut u8 {
        somehal::mem::phys_to_virt(phys as _)
    }

    fn page_size() -> usize {
        somehal::mem::page_size()
    }

    fn memory_map() -> StackVec<MemoryDescriptor, 64> {
        somehal::mem::memory_map()
    }
}
}

struct CpuImpl;

impl_trait! {
impl Cpu for CpuImpl {
    fn current_cpu_id() -> usize {
        todo!()
    }

    fn irq_all_is_enabled() -> bool {
        somehal::irq::irq_all_is_enabled()
    }

    fn irq_all_set_enable(enable: bool) {
        somehal::irq::irq_all_set_enable(enable);
    }


    fn timer_irq() -> usize {
        somehal::irq::timer_irq()
    }
}
}

struct ConsoleImpl;

impl_trait! {
impl Console for ConsoleImpl {
    fn early_write(bytes: &[u8]) -> usize {
        somehal::console::_write_bytes(bytes)
    }

    fn early_read() -> Option<u8> {
        None
    }
}
}

#[unsafe(no_mangle)]
pub extern "Rust" fn _somehal_handle_irq(hwirq: usize) {
    handle_irq(hwirq);
}

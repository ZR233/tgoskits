pub use heapless::Vec as StackVec;
pub use kernutil::memory::MemoryDescriptor;

#[trait_ffi::def_extern_trait(mod_path = "hal::al")]
pub trait Memory {
    /// Convert virtual address to physical address
    /// # Safety
    /// The caller must ensure that the provided virtual address is valid and mapped.
    unsafe fn virt_to_phys(virt: *mut u8) -> usize;
    fn phys_to_virt(phys: usize) -> *mut u8;
    fn page_size() -> usize;
    fn memory_map() -> StackVec<MemoryDescriptor, 64>;
}

#[trait_ffi::def_extern_trait(not_def_impl, mod_path = "hal::al")]
pub trait Platform {
    fn post_allocator();
    fn irq_is_enabled(irq: usize) -> bool;
    fn irq_set_enabled(irq: usize, enabled: bool);
    fn shutdown() -> !;
}

#[trait_ffi::def_extern_trait(not_def_impl, mod_path = "hal::al")]
pub trait Cpu {
    fn current_cpu_id() -> usize;
    fn irq_all_is_enabled() -> bool;
    fn irq_all_set_enable(enabled: bool);
    fn timer_irq() -> usize;
}

#[trait_ffi::def_extern_trait(mod_path = "hal::al", not_def_impl)]
pub trait Console {
    fn early_write(bytes: &[u8]) -> usize;
    fn early_read() -> Option<u8>;
}

pub fn handle_irq(irq_number: usize) {}

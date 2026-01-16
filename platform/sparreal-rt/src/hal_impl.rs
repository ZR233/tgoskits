use alloc::boxed::Box;
use core::ptr::{NonNull, slice_from_raw_parts};
use core::time::Duration;

use someboot::{MemConfig, irq_handler, mem::PteConfig};
use sparreal_kernel::hal::al::AccessFlags;
use sparreal_kernel::{hal::al::*, impl_trait, os::mem::KernelAllocator};

struct InitImpl;

impl_trait! {
impl Platform for InitImpl {
    fn post_allocator() {
        someboot::post_allocator();
    }
    fn shutdown() -> ! {
        someboot::power::shutdown()
    }
    fn irq_is_enabled(irq: IrqId) -> bool {
        someboot::irq::irq_is_enabled(irq.raw().into())
    }
    fn irq_set_enabled(irq: IrqId, enable: bool) {
        someboot::irq::irq_set_enable(irq.raw().into(), enable);
    }

    fn fdt_addr() -> Option<NonNull<u8>> {
        someboot::fdt_addr().map(|ptr| unsafe{ NonNull::new_unchecked(ptr)})
    }

    fn driver_registers() -> DriverRegisterSlice {
        DriverRegisterSlice::from_raw(driver_registers())
    }
}
}

fn driver_registers() -> &'static [u8] {
    unsafe extern "C" {
        fn _sdriver();
        fn _edriver();
    }

    unsafe {
        &*slice_from_raw_parts(
            _sdriver as *const () as *const u8,
            _edriver as *const () as usize - _sdriver as *const () as usize,
        )
    }
}

struct MemoryImpl;

impl_trait! {
impl Memory for MemoryImpl {
    fn _va(paddr: PhysAddr) -> VirtAddr {
        someboot::mem::__va(paddr.raw() as _).into()
    }
    fn _io(paddr: PhysAddr) -> VirtAddr {
        someboot::mem::__io(paddr.raw() as _).into()
    }

    fn kimage_offset() -> isize {
        someboot::mem::vm_load_offset()
    }

    fn virt_to_phys(virt: VirtAddr) -> PhysAddr {
        someboot::mem::virt_to_phys(virt.raw() as _).into()
    }

    fn page_size() -> usize {
        someboot::mem::page_size()
    }

    fn memory_map() -> &'static[ MemoryDescriptor] {
        someboot::mem::memory_map()
    }

    fn page_table_new() -> Result< Box<dyn PageTable>, PagingError> {
        Ok(Box::new( PageTableImpl( someboot::mem::mmu::new_page_table(KernelAllocator)?)))
    }

    fn kernel_page_table() -> PhysAddr {
        let paddr = someboot::kernel_page_table_paddr();
        PhysAddr::new(paddr)
    }

    fn set_kernel_page_table(pt: PhysAddr) {
        someboot::set_kernel_page_table_paddr(pt.raw());
    }

    fn user_page_table() -> PageTableInfo {
        someboot::user_page_table()
    }

    fn set_user_page_table(pt: PageTableInfo) {
        someboot::set_user_page_table(pt);
    }


}
}

pub struct PageTableImpl(someboot::mem::mmu::ArchPageTable<KernelAllocator>);

impl PageTable for PageTableImpl {
    fn addr(&self) -> PhysAddr {
        PhysAddr::new(self.0.root_paddr().raw())
    }

    fn map(
        &mut self,
        virt_start: VirtAddr,
        phys_start: PhysAddr,
        size: usize,
        settings: MemConfig,
        flush: bool,
    ) -> Result<(), PagingError> {
        let pte = PteConfig {
            valid: true,
            read: true,
            writable: settings.access.contains(AccessFlags::WRITE),
            executable: settings.access.contains(AccessFlags::EXECUTE),
            mem_attr: settings.attrs,
            ..Default::default()
        };

        self.0.map(&someboot::mem::MapConfig {
            vaddr: virt_start.raw().into(),
            paddr: phys_start.raw().into(),
            size,
            pte,
            allow_huge: true,
            flush,
        })
    }

    fn unmap(&mut self, virt_start: VirtAddr, size: usize) -> Result<(), PagingError> {
        self.0.unmap(virt_start.raw().into(), size)
    }
}

struct CpuImpl;

impl_trait! {
impl Cpu for CpuImpl {
    fn current_cpu_id() -> usize {
        0 // TODO: implement
    }

    fn irq_local_is_enabled() -> bool {
        someboot::irq::irq_local_is_enabled()
    }

    fn irq_local_set_enable(enable: bool) {
        someboot::irq::irq_local_set_enable(enable);
    }

    fn systimer_irq() -> IrqId {
        someboot::irq::systimer_irq().raw().into()
    }

    fn systimer_enable() {
        someboot::timer::enable();
    }

    fn systimer_irq_enable() {
        someboot::timer::irq_enable();
    }

    fn systimer_irq_disable() {
        someboot::timer::irq_disable();
    }

    fn systimer_irq_is_enabled() -> bool {
        someboot::timer::irq_is_enabled()
    }

    fn systimer_set_next_event(interval: Duration) {
        someboot::timer::set_next_event(interval);
    }
    fn systimer_ack() {
        someboot::timer::ack();
    }
    fn systimer_since_boot() -> Duration {
        someboot::timer::since_boot()
    }
}
}

struct ConsoleImpl;

impl_trait! {
impl Console for ConsoleImpl {
    fn early_write(bytes: &[u8]) -> usize {
        someboot::console::_write_bytes(bytes)
    }

    fn early_read() -> Option<u8> {
        None
    }
}
}

#[irq_handler]
fn somehal_handle_irq(irq: someboot::irq::IrqId) {
    handle_irq(irq.raw().into());
}

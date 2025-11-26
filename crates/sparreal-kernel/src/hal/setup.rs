use crate::hal::{al, timer};

pub fn start_kernel() -> ! {
    crate::os::logger::init();
    info!("Setting up allocator...");

    crate::os::mem::init_heap(&al::memory::memory_map());
    al::platform::post_allocator();
    timer::init();

    al::cpu::irq_all_set_enable(true);

    unsafe extern "C" {
        fn __sparreal_main();
    }

    unsafe { __sparreal_main() };

    al::platform::shutdown()
}

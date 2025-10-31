#[unsafe(no_mangle)]
pub unsafe extern "C" fn kernel_entry() -> ! {
    unimplemented!()
}

pub(crate) fn efi_kernel_prepare() {
    println!("Preparing kernel entry...");
}

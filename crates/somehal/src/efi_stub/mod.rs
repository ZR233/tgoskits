use core::fmt::Write;

use uefi::{
    prelude::*,
    proto::loaded_image::LoadedImage,
    system::with_config_table,
    table::cfg::{ACPI_GUID, ACPI2_GUID, ConfigTableEntry},
};
use uefi_raw::table::system::SystemTable;

use crate::arch::relocate;

pub mod pe;

/// EFI PE 入口点 - 符合 EFI ABI 的汇编包装
/// 参数: a0 = image_handle, a1 = system_table
#[unsafe(export_name = "efi_pe_entry")]
#[unsafe(link_section = ".text")]
pub unsafe extern "C" fn efi_pe_entry(
    image_handle: Handle,
    system_table: *const SystemTable,
) -> Status {
    unsafe {
        relocate();
        ::uefi::boot::set_image_handle(image_handle);
        ::uefi::table::set_system_table(system_table);

        crate::console::set_printer(&UefiPrinter);

        crate::arch::entry::efi_kernel_prepare();
    }

    // 返回成功状态
    Status::SUCCESS
}

struct UefiPrinter;
impl crate::console::Printer for UefiPrinter {
    fn read_byte(&self) -> Option<u8> {
        // system::with_stdin(|stdin| {
        //     let mut buffer = [0u16; 1];
        //     match stdin.read_key(&mut buffer) {
        //         Ok(()) => Some(buffer[0] as u8),
        //         Err(_) => None,
        //     }
        // })
        None
    }

    fn write_str(&self, s: &str) {
        system::with_stdout(|stdout| {
            let _ = stdout.write_str(s);
        });
    }
}

fn get_acpi_rsdp() -> Option<*const u8> {
    with_config_table(|config_table| {
        for entry in config_table {
            if entry.guid == ACPI2_GUID {
                // ACPI 2.0 RSDP (推荐)
                println!("Found ACPI 2.0 RSDP at address: {:p}", entry.address);
                return Some(entry.address as *const u8);
            } else if entry.guid == ACPI_GUID {
                // ACPI 1.0 RSDP (备选)
                println!("Found ACPI 1.0 RSDP at address: {:p}", entry.address);
                return Some(entry.address as *const u8);
            }
        }
        None
    })
}

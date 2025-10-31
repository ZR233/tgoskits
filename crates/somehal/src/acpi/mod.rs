use acpi::{Handle, Handler};

#[derive(Clone)]
struct AcpiHandle;

impl Handler for AcpiHandle {
    unsafe fn map_physical_region<T>(
        &self,
        physical_address: usize,
        size: usize,
    ) -> acpi::PhysicalMapping<Self, T> {
        
    }

    fn unmap_physical_region<T>(region: &acpi::PhysicalMapping<Self, T>) {
        todo!()
    }

    fn read_u8(&self, acpi::address: usize) -> u8 {
        todo!()
    }

    fn read_u16(&self, acpi::address: usize) -> u16 {
        todo!()
    }

    fn read_u32(&self, acpi::address: usize) -> u32 {
        todo!()
    }

    fn read_u64(&self, acpi::address: usize) -> u64 {
        todo!()
    }

    fn write_u8(&self, acpi::address: usize, value: u8) {
        todo!()
    }

    fn write_u16(&self, acpi::address: usize, value: u16) {
        todo!()
    }

    fn write_u32(&self, acpi::address: usize, value: u32) {
        todo!()
    }

    fn write_u64(&self, acpi::address: usize, value: u64) {
        todo!()
    }

    fn read_io_u8(&self, port: u16) -> u8 {
        todo!()
    }

    fn read_io_u16(&self, port: u16) -> u16 {
        todo!()
    }

    fn read_io_u32(&self, port: u16) -> u32 {
        todo!()
    }

    fn write_io_u8(&self, port: u16, value: u8) {
        todo!()
    }

    fn write_io_u16(&self, port: u16, value: u16) {
        todo!()
    }

    fn write_io_u32(&self, port: u16, value: u32) {
        todo!()
    }

    fn read_pci_u8(&self, acpi::address: acpi::PciAddress, offset: u16) -> u8 {
        todo!()
    }

    fn read_pci_u16(&self, acpi::address: acpi::PciAddress, offset: u16) -> u16 {
        todo!()
    }

    fn read_pci_u32(&self, acpi::address: acpi::PciAddress, offset: u16) -> u32 {
        todo!()
    }

    fn write_pci_u8(&self, acpi::address: acpi::PciAddress, offset: u16, value: u8) {
        todo!()
    }

    fn write_pci_u16(&self, acpi::address: acpi::PciAddress, offset: u16, value: u16) {
        todo!()
    }

    fn write_pci_u32(&self, acpi::address: acpi::PciAddress, offset: u16, value: u32) {
        todo!()
    }

    fn nanos_since_boot(&self) -> u64 {
        todo!()
    }

    fn stall(&self, microseconds: u64) {
        todo!()
    }

    fn sleep(&self, milliseconds: u64) {
        todo!()
    }

    fn create_mutex(&self) -> Handle {
        todo!()
    }

    fn acquire(&self, mutex: Handle, timeout: u16) -> Result<(), acpi::aml::AmlError> {
        todo!()
    }

    fn release(&self, mutex: Handle) {
        todo!()
    }
}

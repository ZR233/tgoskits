use page_table_generic::{PageTableEntry, TableGeneric};

pub fn setup() {
    
}

#[derive(Clone, Copy)]
pub struct Generic;

impl TableGeneric for Generic {
    type P;

    const PAGE_SIZE: usize;

    const LEVEL_BITS: &[usize];

    const MAX_BLOCK_LEVEL: usize;

    fn flush(vaddr: Option<page_table_generic::VirtAddr>) {
        todo!()
    }
}

#[derive(Clone, Copy)]
#[repr(transparent)]
pub struct Entry(usize);

impl PageTableEntry for Entry {
    fn valid(&self) -> bool {
        todo!()
    }

    fn paddr(&self) -> page_table_generic::PhysAddr {
        todo!()
    }

    fn set_paddr(&mut self, paddr: page_table_generic::PhysAddr) {
        todo!()
    }

    fn set_valid(&mut self, valid: bool) {
        todo!()
    }

    fn is_huge(&self) -> bool {
        todo!()
    }

    fn set_is_huge(&mut self, b: bool) {
        todo!()
    }
}

impl core::fmt::Debug for Entry {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        todo!()
    }
}

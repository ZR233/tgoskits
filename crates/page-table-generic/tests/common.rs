//! page-table-generic 标准环境测试
//!
//! 这些测试只在有操作系统支持的标准环境下运行，使用完整的 std 库


use page_table_generic::*;

// 简单的测试用PTE实现
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TestPte {
    bits: usize,
}

impl TestPte {
    pub fn new() -> Self {
        Self { bits: 0 }
    }

    pub fn with_flags(valid: bool, is_huge: bool) -> Self {
        let mut pte = Self::new();
        if valid { pte.bits |= 1 << 63; }
        if is_huge { pte.bits |= 1 << 10; }
        pte
    }
}

impl PageTableEntry for TestPte {
    fn valid(&self) -> bool {
        self.bits & (1 << 63) != 0
    }

    fn paddr(&self) -> PhysAddr {
        PhysAddr::new(self.bits & ((1 << 48) - 1))
    }

    fn set_paddr(&mut self, paddr: PhysAddr) {
        self.bits = (self.bits & !((1 << 48) - 1)) | (paddr.raw() & ((1 << 48) - 1));
    }

    fn set_valid(&mut self, valid: bool) {
        if valid {
            self.bits |= 1 << 63;
        } else {
            self.bits &= !(1 << 63);
        }
    }

    fn is_huge(&self) -> bool {
        self.bits & (1 << 10) != 0
    }

    fn set_is_huge(&mut self, huge: bool) {
        if huge {
            self.bits |= 1 << 10;
        } else {
            self.bits &= !(1 << 10);
        }
    }
}

// 测试用页表配置
#[derive(Debug, Clone, Copy)]
pub struct TestTable4KB;

impl TableGeneric for TestTable4KB {
    type P = TestPte;

    const PAGE_SIZE: usize = 4096;    // 4KB
    const LEVEL: usize = 4;           // 4级页表
    const MAX_BLOCK_LEVEL: usize = 2; // 支持大页到第2级

    fn flush(_vaddr: Option<VirtAddr>) {
        // 模拟TLB刷新
        println!("TLB flushed");
    }
}

#[derive(Debug, Clone, Copy)]
pub struct TestTable16KB;

impl TableGeneric for TestTable16KB {
    type P = TestPte;

    const PAGE_SIZE: usize = 16384;   // 16KB
    const LEVEL: usize = 3;           // 3级页表
    const MAX_BLOCK_LEVEL: usize = 1; // 有限大页支持

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("TLB flushed for 16KB pages");
    }
}

// 简单的Copy测试分配器，使用静态计数器
#[derive(Debug, Clone, Copy)]
pub struct StdTestAllocator {
    start_addr: usize,
}

impl StdTestAllocator {
    pub fn new() -> Self {
        Self { start_addr: 0x1000000 } // 从16MB开始
    }

    pub fn with_start(start_addr: usize) -> Self {
        Self { start_addr }
    }
}

impl FramAllocator for StdTestAllocator {
    fn alloc_frame(&self) -> Option<PhysAddr> {
        // 使用简单的静态分配策略
        // 在实际测试中，这里可以根据需要实现更复杂的分配逻辑
        static mut NEXT_FRAME: usize = 0x1000000;

        unsafe {
            let addr = NEXT_FRAME;
            NEXT_FRAME += 0x1000; // 4KB页面
            if addr < 0x2000000 { // 限制分配范围
                Some(PhysAddr::new(addr))
            } else {
                None
            }
        }
    }

    fn dealloc_frame(&self, _frame: PhysAddr) {
        // 简单实现，不进行实际的内存回收
        println!("Deallocated frame at {:#x}", _frame.raw());
    }

    fn phys_to_virt(&self, paddr: PhysAddr) -> *mut u8 {
        // 在测试中，我们使用一个假的虚拟地址映射
        // 实际映射在真实操作系统中由内核管理
        // 这里我们返回一个安全的指针用于测试
        use std::alloc::{alloc, dealloc, Layout};

        // 为每个物理地址分配真实的内存用于测试
        let layout = Layout::from_size_align(0x1000, 0x1000).unwrap();
        let ptr = unsafe { alloc(layout) };

        // 如果分配失败，返回一个假的指针（可能会导致panic，但这只是测试）
        if ptr.is_null() {
            // 返回一个假的地址，只是为了让测试能编译通过
            std::ptr::NonNull::dangling().as_ptr()
        } else {
            ptr
        }
    }
}

// 兼容性辅助函数，用于现有测试
pub fn create_basic_4kb_config(vaddr: usize, paddr: usize, size: usize) -> MapConfig<TestPte> {
    MapConfig {
        vaddr: VirtAddr::new(vaddr),
        paddr: PhysAddr::new(paddr),
        size,
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    }
}

pub fn create_basic_4kb_config_no_huge(vaddr: usize, paddr: usize, size: usize) -> MapConfig<TestPte> {
    MapConfig {
        vaddr: VirtAddr::new(vaddr),
        paddr: PhysAddr::new(paddr),
        size,
        pte: TestPte::with_flags(true, false),
        allow_huge: false,
        flush: false,
    }
}

// 为16KB页面创建配置
pub fn create_16kb_config(vaddr: usize, paddr: usize, size: usize) -> MapConfig<TestPte> {
    MapConfig {
        vaddr: VirtAddr::new(vaddr),
        paddr: PhysAddr::new(paddr),
        size,
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    }
}
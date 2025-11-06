//! 基本的页表映射测试

#![no_std]

extern crate page_table_generic;
use page_table_generic::*;

// 简单的模拟实现
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct MockPte {
    bits: usize,
}

impl MockPte {
    fn new() -> Self {
        Self { bits: 0 }
    }
}

impl PageTableEntry for MockPte {
    fn valid(&self) -> bool {
        self.bits & (1 << 0) != 0
    }

    fn paddr(&self) -> PhysAddr {
        PhysAddr::new(self.bits & !((1 << 12) - 1))
    }

    fn set_paddr(&mut self, paddr: PhysAddr) {
        self.bits = (self.bits & ((1 << 12) - 1)) | (paddr.raw() & !((1 << 12) - 1));
    }

    fn set_valid(&mut self, valid: bool) {
        if valid {
            self.bits |= 1 << 0;
        } else {
            self.bits &= !(1 << 0);
        }
    }

    fn is_huge(&self) -> bool {
        self.bits & (1 << 1) != 0
    }

    fn set_is_huge(&mut self, huge: bool) {
        if huge {
            self.bits |= 1 << 1;
        } else {
            self.bits &= !(1 << 1);
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct MockTableGeneric;

impl TableGeneric for MockTableGeneric {
    type P = MockPte;

    const LEVEL: usize = 4;
    const MAX_BLOCK_LEVEL: usize = 2;

    fn flush(_vaddr: Option<VirtAddr>) {
        // 模拟TLB刷新
    }
}

#[derive(Debug, Clone)]
struct TestAllocator {
    next_addr: usize,
}

impl TestAllocator {
    fn new() -> Self {
        Self { next_addr: 0x1000000 }
    }
}

impl Clone for TestAllocator {
    fn clone(&self) -> Self {
        Self { next_addr: self.next_addr }
    }
}

impl Copy for TestAllocator {}

impl FramAllocator for TestAllocator {
    fn alloc_frame(&self) -> Option<PhysAddr> {
        Some(PhysAddr::new(self.next_addr))
    }

    fn dealloc_frame(&self, _frame: PhysAddr) {
        // 模拟释放
    }

    fn phys_to_virt(&self, paddr: PhysAddr) -> *mut u8 {
        paddr.raw() as *mut u8
    }
}

#[test]
fn test_basic_mapping() {
    let allocator = TestAllocator::new();
    let mut page_table = PageTable::<MockTableGeneric, TestAllocator>::new(allocator)
        .expect("Failed to create page table");

    let config = MapConfig {
        vaddr: VirtAddr::new(0x1000000),
        paddr: PhysAddr::new(0x2000000),
        size: 0x1000,
        pte: MockPte::new(),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Basic mapping should succeed: {:?}", result);
}

#[test]
fn test_address_calculations() {
    // 测试地址计算函数
    let vaddr = VirtAddr::new(0x123456789ABCDEF0);

    // 测试不同级别的索引计算
    let index1 = MockTableGeneric::virt_to_index(vaddr, 1);
    let index2 = MockTableGeneric::virt_to_index(vaddr, 2);
    let index3 = MockTableGeneric::virt_to_index(vaddr, 3);
    let index4 = MockTableGeneric::virt_to_index(vaddr, 4);

    // 验证索引在有效范围内
    assert!(index1 < 512);
    assert!(index2 < 512);
    assert!(index3 < 512);
    assert!(index4 < 512);

    // 测试级别大小
    let size1 = MockTableGeneric::level_size(1);
    let size4 = MockTableGeneric::level_size(4);

    assert_eq!(size1, 0x1000); // 页级别
    assert_eq!(size4, 0x1000); // 最低级别也是页大小
}

#[test]
fn test_alignment_checks() {
    let vaddr_aligned = VirtAddr::new(0x200000); // 2MB对齐
    let vaddr_unaligned = VirtAddr::new(0x200001);
    let paddr_aligned = PhysAddr::new(0x300000); // 2MB对齐
    let paddr_unaligned = PhysAddr::new(0x300001);

    // 测试2MB级别对齐
    assert!(MockTableGeneric::is_vaddr_aligned(vaddr_aligned, 0x200000, 2));
    assert!(!MockTableGeneric::is_vaddr_aligned(vaddr_unaligned, 0x200000, 2));
    assert!(MockTableGeneric::is_paddr_aligned(paddr_aligned, 0x200000, 2));
    assert!(!MockTableGeneric::is_paddr_aligned(paddr_unaligned, 0x200000, 2));
}
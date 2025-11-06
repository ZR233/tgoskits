#![no_std]

use core::fmt::Debug;

mod def;
mod table;

#[cfg(all(test, not(target_os = "none")))]
pub mod mock;

pub use def::*;
pub use table::*;

pub type PagingResult<T = ()> = Result<T, PagingError>;

pub trait FramAllocator: Clone + Copy + Sync + Send + 'static {
    fn alloc_frame(&self) -> Option<PhysAddr>;

    fn dealloc_frame(&self, frame: PhysAddr);

    fn phys_to_virt(&self, paddr: PhysAddr) -> *mut u8;
}

pub trait TableGeneric: Sync + Send + Clone + Copy + 'static {
    type P: PageTableEntry;

    /// 页面大小（支持4KB、16KB、64KB等）
    const PAGE_SIZE: usize;
    /// 页表级别数（支持3级、4级、5级等）
    const LEVEL: usize;
    /// 大页最高支持的级别
    const MAX_BLOCK_LEVEL: usize;
    /// 有效地址位数
    const VALID_BITS: usize = Self::PAGE_SIZE.trailing_zeros() as usize + Self::LEVEL * 9;
    /// 每个页表的条目数
    const TABLE_LEN: usize = Self::PAGE_SIZE / core::mem::size_of::<Self::P>();

    /// 刷新TLB
    fn flush(vaddr: Option<VirtAddr>);
}

pub trait PageTableEntry: Debug + Sync + Send + Clone + Copy + Sized + 'static {
    fn valid(&self) -> bool;
    fn paddr(&self) -> PhysAddr;
    fn set_paddr(&mut self, paddr: PhysAddr);
    fn set_valid(&mut self, valid: bool);
    fn is_huge(&self) -> bool;
    fn set_is_huge(&mut self, b: bool);
}

/// 常用架构配置的辅助trait
pub trait ArchitectureConfig {
    /// 默认的页表配置类型
    type Config: TableGeneric;

    /// 获取架构名称
    fn architecture_name() -> &'static str;

    /// 获取页面大小（字节）
    fn page_size() -> usize {
        Self::Config::PAGE_SIZE
    }

    /// 获取页表级别数
    fn levels() -> usize {
        Self::Config::LEVEL
    }
}

/// x86_64架构配置（4KB页面，4级页表）
pub struct X86_64Config;

impl ArchitectureConfig for X86_64Config {
    type Config = crate::examples::X86_64Table;

    fn architecture_name() -> &'static str {
        "x86_64"
    }
}

/// ARM64架构配置（4KB页面，4级页表）
pub struct ARM64Config;

impl ArchitectureConfig for ARM64Config {
    type Config = crate::examples::ARM64Table;

    fn architecture_name() -> &'static str {
        "ARM64"
    }
}

/// RISC-V架构配置（4KB页面，3级页表）
pub struct RISCV64Config;

impl ArchitectureConfig for RISCV64Config {
    type Config = crate::examples::RISCV64Table;

    fn architecture_name() -> &'static str {
        "RISC-V 64-bit"
    }
}

/// 公共Mock实现，用于示例和测试
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MockPte {
    bits: usize,
}

impl MockPte {
    pub fn new() -> Self {
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

/// 示例架构实现模块
///
/// 这些示例展示了如何为不同CPU架构配置页表映射。
/// 在实际使用中，您需要根据具体的架构和需求来实现相应的配置。
pub mod examples {
    use super::*;

    /// x86_64架构示例（4KB页面，4级页表）
    #[derive(Debug, Clone, Copy)]
    pub struct X86_64Table;

    impl TableGeneric for X86_64Table {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 4;
        const MAX_BLOCK_LEVEL: usize = 2;

        fn flush(_vaddr: Option<VirtAddr>) {
            // x86_64的TLB刷新实现
            // 在实际实现中，这里会调用相应的汇编指令
        }
    }

    /// ARM64架构示例（4KB页面，4级页表）
    #[derive(Debug, Clone, Copy)]
    pub struct ARM64Table;

    impl TableGeneric for ARM64Table {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 4;
        const MAX_BLOCK_LEVEL: usize = 2;

        fn flush(_vaddr: Option<VirtAddr>) {
            // ARM64的TLB刷新实现
            // 在实际实现中，这里会调用相应的汇编指令
        }
    }

    /// ARM64大页面架构示例（16KB页面，3级页表）
    #[derive(Debug, Clone, Copy)]
    pub struct ARM64LargeTable;

    impl TableGeneric for ARM64LargeTable {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 16384; // 16KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

        fn flush(_vaddr: Option<VirtAddr>) {
            // ARM64大页面的TLB刷新实现
        }
    }

    /// RISC-V架构示例（4KB页面，3级页表）
    #[derive(Debug, Clone, Copy)]
    pub struct RISCV64Table;

    impl TableGeneric for RISCV64Table {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

        fn flush(_vaddr: Option<VirtAddr>) {
            // RISC-V的TLB刷新实现 (sfence.vma)
        }
    }

    /// 自定义大页面架构示例（64KB页面，3级页表）
    #[derive(Debug, Clone, Copy)]
    pub struct LargePageTable;

    impl TableGeneric for LargePageTable {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 65536; // 64KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

        fn flush(_vaddr: Option<VirtAddr>) {
            // 自定义大页面的TLB刷新实现
        }
    }

    /// 3级页表架构示例（适用于简化场景）
    #[derive(Debug, Clone, Copy)]
    pub struct ThreeLevelTable;

    impl TableGeneric for ThreeLevelTable {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

        fn flush(_vaddr: Option<VirtAddr>) {
            // 3级页表的TLB刷新实现
        }
    }

    /// 5级页表架构示例（支持超大虚拟地址空间）
    #[derive(Debug, Clone, Copy)]
    pub struct FiveLevelTable;

    impl TableGeneric for FiveLevelTable {
        type P = super::MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 5;
        const MAX_BLOCK_LEVEL: usize = 3;

        fn flush(_vaddr: Option<VirtAddr>) {
            // 5级页表的TLB刷新实现
        }
    }
}

#[cfg(all(test, not(target_os = "none")))]
mod tests {
    use super::*;
    extern crate std;

    #[derive(Debug, Clone, Copy)]
    struct MockTableGeneric4KB;

    impl TableGeneric for MockTableGeneric4KB {
        type P = MockPte;

        const PAGE_SIZE: usize = 4096; // 4KB
        const LEVEL: usize = 4;
        const MAX_BLOCK_LEVEL: usize = 2;

        fn flush(_vaddr: Option<VirtAddr>) {
            // 模拟TLB刷新
        }
    }

    #[derive(Debug, Clone, Copy)]
    struct MockTableGeneric16KB;

    impl TableGeneric for MockTableGeneric16KB {
        type P = MockPte;

        const PAGE_SIZE: usize = 16384; // 16KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

        fn flush(_vaddr: Option<VirtAddr>) {
            // 模拟TLB刷新
        }
    }

    #[derive(Debug, Clone, Copy)]
    struct MockTableGeneric64KB;

    impl TableGeneric for MockTableGeneric64KB {
        type P = MockPte;

        const PAGE_SIZE: usize = 65536; // 64KB
        const LEVEL: usize = 3;
        const MAX_BLOCK_LEVEL: usize = 1;

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
    fn test_debug_implementations() {
        let allocator = TestAllocator::new();
        let page_table = PageTable::<MockTableGeneric4KB, TestAllocator>::new(allocator)
            .expect("Failed to create page table");

        let config = MapConfig {
            vaddr: VirtAddr::new(0x1000000),
            paddr: PhysAddr::new(0x2000000),
            size: 0x1000,
            pte: MockPte::new(),
            allow_huge: true,
            flush: false,
        };

        // 测试Debug trait实现
        println!("PageTable: {:?}", page_table);
        println!("Config: {:?}", config);

        // 测试错误类型的Debug
        let error = PagingError::alignment_error("test alignment");
        println!("Error: {:?}", error);

        let conflict_error = PagingError::mapping_conflict(
            VirtAddr::new(0x1000),
            PhysAddr::new(0x2000)
        );
        println!("Conflict Error: {:?}", conflict_error);
    }

    #[test]
    fn test_different_page_sizes() {
        let vaddr = VirtAddr::new(0x123456789ABCDEF0);

        // 测试4KB页面
        let index4kb_1 = MockTableGeneric4KB::virt_to_index(vaddr, 1);
        let index4kb_4 = MockTableGeneric4KB::virt_to_index(vaddr, 4);
        let size4kb_1 = MockTableGeneric4KB::level_size(1);
        let size4kb_4 = MockTableGeneric4KB::level_size(4);

        assert!(index4kb_1 < 512);
        assert!(index4kb_4 < 512);
        assert_eq!(size4kb_1, 0x200000); // 大页级别
        assert_eq!(size4kb_4, 4096); // 页级别

        // 测试16KB页面
        let index16kb_1 = MockTableGeneric16KB::virt_to_index(vaddr, 1);
        let index16kb_3 = MockTableGeneric16KB::virt_to_index(vaddr, 3);
        let size16kb_1 = MockTableGeneric16KB::level_size(1);
        let size16kb_3 = MockTableGeneric16KB::level_size(3);

        assert!(index16kb_1 < 512);
        assert!(index16kb_3 < 512);
        assert_eq!(size16kb_1, 0x800000); // 大页级别
        assert_eq!(size16kb_3, 16384); // 页级别

        // 测试64KB页面
        let index64kb_1 = MockTableGeneric64KB::virt_to_index(vaddr, 1);
        let index64kb_3 = MockTableGeneric64KB::virt_to_index(vaddr, 3);
        let size64kb_1 = MockTableGeneric64KB::level_size(1);
        let size64kb_3 = MockTableGeneric64KB::level_size(3);

        assert!(index64kb_1 < 512);
        assert!(index64kb_3 < 512);
        assert_eq!(size64kb_1, 0x2000000); // 大页级别
        assert_eq!(size64kb_3, 65536); // 页级别
    }

    #[test]
    fn test_alignment_checks_different_page_sizes() {
        // 4KB页面对齐测试
        let vaddr_aligned_4kb = VirtAddr::new(0x1000); // 4KB对齐
        let vaddr_unaligned_4kb = VirtAddr::new(0x1001);

        assert!(MockTableGeneric4KB::is_vaddr_aligned(vaddr_aligned_4kb, 4096, 4));
        assert!(!MockTableGeneric4KB::is_vaddr_aligned(vaddr_unaligned_4kb, 4096, 4));

        // 16KB页面对齐测试
        let vaddr_aligned_16kb = VirtAddr::new(0x4000); // 16KB对齐
        let vaddr_unaligned_16kb = VirtAddr::new(0x4001);

        assert!(MockTableGeneric16KB::is_vaddr_aligned(vaddr_aligned_16kb, 16384, 3));
        assert!(!MockTableGeneric16KB::is_vaddr_aligned(vaddr_unaligned_16kb, 16384, 3));

        // 64KB页面对齐测试
        let vaddr_aligned_64kb = VirtAddr::new(0x10000); // 64KB对齐
        let vaddr_unaligned_64kb = VirtAddr::new(0x10001);

        assert!(MockTableGeneric64KB::is_vaddr_aligned(vaddr_aligned_64kb, 65536, 3));
        assert!(!MockTableGeneric64KB::is_vaddr_aligned(vaddr_unaligned_64kb, 65536, 3));
    }

    #[test]
    fn test_basic_mapping_different_configs() {
        // 4KB页面映射测试
        let allocator = TestAllocator::new();
        let mut page_table_4kb = PageTable::<MockTableGeneric4KB, TestAllocator>::new(allocator)
            .expect("Failed to create 4KB page table");

        let config_4kb = MapConfig {
            vaddr: VirtAddr::new(0x1000000),
            paddr: PhysAddr::new(0x2000000),
            size: 4096,
            pte: MockPte::new(),
            allow_huge: true,
            flush: false,
        };

        let result_4kb = page_table_4kb.map(&config_4kb);
        assert!(result_4kb.is_ok(), "4KB mapping should succeed: {:?}", result_4kb);

        // 16KB页面映射测试
        let allocator = TestAllocator::new();
        let mut page_table_16kb = PageTable::<MockTableGeneric16KB, TestAllocator>::new(allocator)
            .expect("Failed to create 16KB page table");

        let config_16kb = MapConfig {
            vaddr: VirtAddr::new(0x2000000),
            paddr: PhysAddr::new(0x3000000),
            size: 16384,
            pte: MockPte::new(),
            allow_huge: true,
            flush: false,
        };

        let result_16kb = page_table_16kb.map(&config_16kb);
        assert!(result_16kb.is_ok(), "16KB mapping should succeed: {:?}", result_16kb);
    }

    #[test]
    fn test_error_types() {
        // 测试对齐错误
        let alignment_error = PagingError::alignment_error("Test alignment failure");
        assert!(matches!(alignment_error, PagingError::AlignmentError { .. }));

        // 测试映射冲突错误
        let conflict_error = PagingError::mapping_conflict(
            VirtAddr::new(0x1000),
            PhysAddr::new(0x2000)
        );
        assert!(matches!(conflict_error, PagingError::MappingConflict { .. }));

        // 测试溢出错误
        let overflow_error = PagingError::address_overflow("Test overflow");
        assert!(matches!(overflow_error, PagingError::AddressOverflow { .. }));

        // 测试无效大小错误
        let size_error = PagingError::invalid_size("Test invalid size");
        assert!(matches!(size_error, PagingError::InvalidSize { .. }));

        // 测试层次结构错误
        let hierarchy_error = PagingError::hierarchy_error("Test hierarchy error");
        assert!(matches!(hierarchy_error, PagingError::HierarchyError { .. }));
    }

    #[test]
    fn test_architecture_configs() {
        // 测试x86_64配置
        assert_eq!(X86_64Config::architecture_name(), "x86_64");
        assert_eq!(X86_64Config::page_size(), 4096);
        assert_eq!(X86_64Config::levels(), 4);

        // 测试ARM64配置
        assert_eq!(ARM64Config::architecture_name(), "ARM64");
        assert_eq!(ARM64Config::page_size(), 4096);
        assert_eq!(ARM64Config::levels(), 4);

        // 测试RISC-V配置
        assert_eq!(RISCV64Config::architecture_name(), "RISC-V 64-bit");
        assert_eq!(RISCV64Config::page_size(), 4096);
        assert_eq!(RISCV64Config::levels(), 3);

        // 创建不同架构的页表
        let _x86_64_table: PageTable<examples::X86_64Table, TestAllocator> =
            PageTable::new(TestAllocator::new()).unwrap();

        let _arm64_table: PageTable<examples::ARM64Table, TestAllocator> =
            PageTable::new(TestAllocator::new()).unwrap();

        let _riscv64_table: PageTable<examples::RISCV64Table, TestAllocator> =
            PageTable::new(TestAllocator::new()).unwrap();
    }
}


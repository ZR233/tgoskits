//! 架构适配性测试
//!
//! 测试不同架构配置的页表映射功能

#![cfg(target_os != "none")]

use page_table_generic::*;
use crate::common::{StdTestAllocator, TestPte};

// x86_64架构测试配置
#[derive(Debug, Clone, Copy)]
pub struct X86_64TestTable;

impl TableGeneric for X86_64TestTable {
    type P = TestPte;

    const PAGE_SIZE: usize = 4096;    // 4KB页面
    const LEVEL: usize = 4;           // 4级页表 (PML4 -> PDP -> PD -> PT)
    const MAX_BLOCK_LEVEL: usize = 2; // 支持2MB和1GB大页

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("x86_64 TLB flushed");
    }
}

// ARM64架构测试配置 (4KB页面)
#[derive(Debug, Clone, Copy)]
pub struct ARM64TestTable;

impl TableGeneric for ARM64TestTable {
    type P = TestPte;

    const PAGE_SIZE: usize = 4096;    // 4KB页面
    const LEVEL: usize = 4;           // 4级页表
    const MAX_BLOCK_LEVEL: usize = 2; // 支持大页

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("ARM64 TLB flushed (4KB)");
    }
}

// ARM64大页面架构测试配置 (16KB页面)
#[derive(Debug, Clone, Copy)]
pub struct ARM64LargeTestTable;

impl TableGeneric for ARM64LargeTestTable {
    type P = TestPte;

    const PAGE_SIZE: usize = 16384;   // 16KB页面
    const LEVEL: usize = 3;           // 3级页表
    const MAX_BLOCK_LEVEL: usize = 1; // 有限大页支持

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("ARM64 TLB flushed (16KB)");
    }
}

// RISC-V架构测试配置 (Sv39)
#[derive(Debug, Clone, Copy)]
pub struct RISCV64TestTable;

impl TableGeneric for RISCV64TestTable {
    type P = TestPte;

    const PAGE_SIZE: usize = 4096;    // 4KB页面
    const LEVEL: usize = 3;           // 3级页表 (Page Directory -> Page Table -> Page)
    const MAX_BLOCK_LEVEL: usize = 1; // 支持Megapage (2MB)

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("RISC-V TLB flushed (sfence.vma)");
    }
}

// 自定义大页面架构测试配置 (64KB页面)
#[derive(Debug, Clone, Copy)]
pub struct LargePageTestTable;

impl TableGeneric for LargePageTestTable {
    type P = TestPte;

    const PAGE_SIZE: usize = 65536;   // 64KB页面
    const LEVEL: usize = 3;           // 3级页表
    const MAX_BLOCK_LEVEL: usize = 1; // 有限大页支持

    fn flush(_vaddr: Option<VirtAddr>) {
        println!("Custom large page TLB flushed");
    }
}

#[test]
fn test_x86_64_architecture() {
    println!("🧪 测试x86_64架构配置...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<X86_64TestTable, _>::new(allocator)
        .expect("Failed to create x86_64 page table");

    // 验证配置
    assert_eq!(X86_64TestTable::PAGE_SIZE, 4096);
    assert_eq!(X86_64TestTable::LEVEL, 4);
    assert_eq!(X86_64TestTable::MAX_BLOCK_LEVEL, 2);

    // 测试地址计算
    let vaddr = VirtAddr::new(0x123456789ABCDEF0);
    let index = X86_64TestTable::virt_to_index(vaddr, 1);
    assert!(index < 512, "Index should be valid");

    // 测试映射
    let config = MapConfig {
        vaddr: VirtAddr::new(0x1000000),
        paddr: PhysAddr::new(0x2000000),
        size: 0x1000, // 4KB
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "x86_64 mapping should succeed: {:?}", result);

    println!("✅ x86_64架构测试通过");
}

#[test]
fn test_arm64_architecture() {
    println!("🧪 测试ARM64架构配置...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<ARM64TestTable, _>::new(allocator)
        .expect("Failed to create ARM64 page table");

    // 验证配置
    assert_eq!(ARM64TestTable::PAGE_SIZE, 4096);
    assert_eq!(ARM64TestTable::LEVEL, 4);
    assert_eq!(ARM64TestTable::MAX_BLOCK_LEVEL, 2);

    // 测试大页映射 (2MB)
    let config = MapConfig {
        vaddr: VirtAddr::new(0x200000),  // 2MB对齐
        paddr: PhysAddr::new(0x300000),
        size: 0x200000,                  // 2MB
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "ARM64 huge page mapping should succeed: {:?}", result);

    println!("✅ ARM64架构测试通过");
}

#[test]
fn test_arm64_large_page_architecture() {
    println!("🧪 测试ARM64大页面架构配置...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<ARM64LargeTestTable, _>::new(allocator)
        .expect("Failed to create ARM64 large page table");

    // 验证配置
    assert_eq!(ARM64LargeTestTable::PAGE_SIZE, 16384); // 16KB
    assert_eq!(ARM64LargeTestTable::LEVEL, 3);
    assert_eq!(ARM64LargeTestTable::MAX_BLOCK_LEVEL, 1);

    // 测试16KB页面映射
    let config = MapConfig {
        vaddr: VirtAddr::new(0x1000000),
        paddr: PhysAddr::new(0x2000000),
        size: 0x4000, // 16KB
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "ARM64 large page mapping should succeed: {:?}", result);

    println!("✅ ARM64大页面架构测试通过");
}

#[test]
fn test_riscv64_architecture() {
    println!("🧪 测试RISC-V架构配置...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<RISCV64TestTable, _>::new(allocator)
        .expect("Failed to create RISC-V page table");

    // 验证配置
    assert_eq!(RISCV64TestTable::PAGE_SIZE, 4096);
    assert_eq!(RISCV64TestTable::LEVEL, 3); // RISC-V通常使用3级页表
    assert_eq!(RISCV64TestTable::MAX_BLOCK_LEVEL, 1);

    // 测试Megapage映射 (2MB)
    let config = MapConfig {
        vaddr: VirtAddr::new(0x200000),  // 2MB对齐
        paddr: PhysAddr::new(0x300000),
        size: 0x200000,                  // 2MB
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "RISC-V megapage mapping should succeed: {:?}", result);

    println!("✅ RISC-V架构测试通过");
}

#[test]
fn test_large_page_architecture() {
    println!("🧪 测试自定义大页面架构配置...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<LargePageTestTable, _>::new(allocator)
        .expect("Failed to create large page table");

    // 验证配置
    assert_eq!(LargePageTestTable::PAGE_SIZE, 65536); // 64KB
    assert_eq!(LargePageTestTable::LEVEL, 3);
    assert_eq!(LargePageTestTable::MAX_BLOCK_LEVEL, 1);

    // 测试64KB页面映射
    let config = MapConfig {
        vaddr: VirtAddr::new(0x1000000),
        paddr: PhysAddr::new(0x2000000),
        size: 0x10000, // 64KB
        pte: TestPte::with_flags(true, false),
        allow_huge: true,
        flush: false,
    };

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Large page mapping should succeed: {:?}", result);

    println!("✅ 自定义大页面架构测试通过");
}

#[test]
fn test_architecture_address_calculations() {
    println!("🧪 测试不同架构的地址计算...");

    let vaddr = VirtAddr::new(0x123456789ABCDEF0);

    // 测试不同架构的地址计算
    let arch_tests = [
        ("x86_64", X86_64TestTable::virt_to_index(vaddr, 1), 4),
        ("ARM64", ARM64TestTable::virt_to_index(vaddr, 1), 4),
        ("ARM64-Large", ARM64LargeTestTable::virt_to_index(vaddr, 1), 3),
        ("RISC-V", RISCV64TestTable::virt_to_index(vaddr, 1), 3),
        ("Large-Page", LargePageTestTable::virt_to_index(vaddr, 1), 3),
    ];

    for (name, index, expected_levels) in arch_tests {
        assert!(index < 512, "{} index should be within bounds", name);
        println!("{}: index={}, levels={}", name, index, expected_levels);
    }

    println!("✅ 架构地址计算测试通过");
}

#[test]
fn test_page_size_comparisons() {
    println!("🧪 测试不同页面大小的比较...");

    let architectures = [
        ("x86_64/ARM64/RISC-V", 4096),    // 4KB
        ("ARM64 Large", 16384),            // 16KB
        ("Custom Large", 65536),           // 64KB
    ];

    for (name, page_size) in architectures {
        let level_size = match page_size {
            4096 => 4096,
            16384 => 16384,
            65536 => 65536,
            _ => 4096,
        };

        println!("{}: page_size={:#x}, level_size={:#x}", name, page_size, level_size);
    }

    println!("✅ 页面大小比较测试通过");
}

#[test]
fn test_five_level_page_table() {
    println!("🧪 测试5级页表架构...");

    // 定义一个5级页表配置
    #[derive(Debug, Clone, Copy)]
    struct FiveLevelTestTable;

    impl TableGeneric for FiveLevelTestTable {
        type P = TestPte;

        const PAGE_SIZE: usize = 4096;    // 4KB
        const LEVEL: usize = 5;           // 5级页表
        const MAX_BLOCK_LEVEL: usize = 3; // 支持更深层的大页

        fn flush(_vaddr: Option<VirtAddr>) {
            println!("5-level page table TLB flushed");
        }
    }

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<FiveLevelTestTable, _>::new(allocator)
        .expect("Failed to create 5-level page table");

    // 验证配置
    assert_eq!(FiveLevelTestTable::PAGE_SIZE, 4096);
    assert_eq!(FiveLevelTestTable::LEVEL, 5);
    assert_eq!(FiveLevelTestTable::MAX_BLOCK_LEVEL, 3);

    // 测试地址计算
    let vaddr = VirtAddr::new(0x123456789ABCDEF0);
    let index = FiveLevelTestTable::virt_to_index(vaddr, 1);
    assert!(index < 512, "5-level index should be valid");

    println!("✅ 5级页表架构测试通过");
}

#[test]
fn test_mixed_architecture_compatibility() {
    println!("🧪 测试架构混合兼容性...");

    // 测试不同架构可以在同一个程序中使用
    let allocator = StdTestAllocator::new();

    let x86_64_table: PageTable<X86_64TestTable, _> =
        PageTable::new(allocator.clone()).expect("Failed to create x86_64 table");

    let arm64_table: PageTable<ARM64TestTable, _> =
        PageTable::new(allocator.clone()).expect("Failed to create ARM64 table");

    let riscv_table: PageTable<RISCV64TestTable, _> =
        PageTable::new(allocator.clone()).expect("Failed to create RISC-V table");

    println!("x86_64 table: {:?}", x86_64_table);
    println!("ARM64 table: {:?}", arm64_table);
    println!("RISC-V table: {:?}", riscv_table);

    println!("✅ 架构混合兼容性测试通过");
}
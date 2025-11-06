//! 标准环境页表映射测试
//!
//! 这些测试只在有操作系统支持的环境下运行，使用完整的 std 库功能

mod common;

use common::*;
use page_table_generic::*;

#[test]
fn test_std_basic_page_mapping() {
    println!("🧪 运行标准环境基础页表映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    let config = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Basic page mapping should succeed: {:?}", result);

    println!("✅ 基础页表映射测试通过");
}

#[test]
fn test_std_large_range_mapping() {
    println!("🧪 运行标准环境大范围映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 测试2MB范围映射
    let config = create_basic_4kb_config(0x1000000, 0x2000000, 0x200000);

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Large range mapping should succeed: {:?}", result);

    println!("✅ 大范围映射测试通过");
}

#[test]
fn test_std_huge_page_mapping() {
    println!("🧪 运行标准环境大页映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 测试对齐的大页映射 (2MB)
    let config = create_basic_4kb_config(0x200000, 0x300000, 0x200000);

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Huge page mapping should succeed: {:?}", result);

    println!("✅ 大页映射测试通过");
}

#[test]
fn test_std_no_huge_mapping() {
    println!("🧪 运行标准环境非大页映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    let config = create_basic_4kb_config_no_huge(0x200000, 0x300000, 0x200000);

    let result = page_table.map(&config);
    assert!(result.is_ok(), "Non-huge mapping should succeed: {:?}", result);

    println!("✅ 非大页映射测试通过");
}

#[test]
fn test_std_unaligned_mapping() {
    println!("🧪 运行标准环境未对齐映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 测试未对齐的地址
    let config = create_basic_4kb_config(0x1000001, 0x2000000, 0x1000);

    let result = page_table.map(&config);
    assert!(result.is_err(), "Unaligned mapping should fail");

    println!("✅ 未对齐映射测试通过");
}

#[test]
fn test_std_zero_size_mapping() {
    println!("🧪 运行标准环境零大小映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    let mut config = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);
    config.size = 0;

    let result = page_table.map(&config);
    assert!(result.is_err(), "Zero size mapping should fail");

    println!("✅ 零大小映射测试通过");
}

#[test]
fn test_std_address_overflow() {
    println!("🧪 运行标准环境地址溢出测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    let config = create_basic_4kb_config(usize::MAX - 0x1000, 0x2000000, 0x2000);

    let result = page_table.map(&config);
    assert!(result.is_err(), "Address overflow should fail");

    println!("✅ 地址溢出测试通过");
}

#[test]
fn test_std_multiple_mappings() {
    println!("🧪 运行标准环境多重映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 映射第一个范围
    let config1 = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);
    let result1 = page_table.map(&config1);
    assert!(result1.is_ok(), "First mapping should succeed");

    // 映射第二个不重叠的范围
    let config2 = create_basic_4kb_config(0x1001000, 0x2001000, 0x1000);
    let result2 = page_table.map(&config2);
    assert!(result2.is_ok(), "Second mapping should succeed");

    println!("✅ 多重映射测试通过");
}

#[test]
fn test_std_duplicate_mapping() {
    println!("🧪 运行标准环境重复映射测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 映射一个范围
    let config1 = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);
    let result1 = page_table.map(&config1);
    assert!(result1.is_ok(), "First mapping should succeed");

    // 尝试映射相同的虚拟地址
    let config2 = create_basic_4kb_config(0x1000000, 0x3000000, 0x1000);
    let result2 = page_table.map(&config2);
    assert!(result2.is_err(), "Duplicate mapping should fail");

    println!("✅ 重复映射测试通过");
}

#[test]
fn test_std_16kb_page_mapping() {
    println!("🧪 运行标准环境16KB页面测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable16KB, _>::new(allocator)
        .expect("Failed to create 16KB page table");

    // 测试16KB页面映射
    let config = create_16kb_config(0x1000000, 0x2000000, 0x4000); // 16KB

    let result = page_table.map(&config);
    assert!(result.is_ok(), "16KB page mapping should succeed: {:?}", result);

    println!("✅ 16KB页面映射测试通过");
}

#[test]
fn test_std_address_calculations() {
    println!("🧪 运行标准环境地址计算测试...");

    let vaddr = VirtAddr::new(0x123456789ABCDEF0);

    // 测试4KB页面的地址计算
    let index_4kb_1 = PageTable::<TestTable4KB, StdTestAllocator>::virt_to_index(vaddr, 1);
    let index_4kb_4 = PageTable::<TestTable4KB, StdTestAllocator>::virt_to_index(vaddr, 4);
    let size_4kb_1 = PageTable::<TestTable4KB, StdTestAllocator>::level_size(1);
    let size_4kb_4 = PageTable::<TestTable4KB, StdTestAllocator>::level_size(4);

    assert!(index_4kb_1 < 512, "Index should be within page table bounds");
    assert!(index_4kb_4 < 512, "Index should be within page table bounds");
    assert_eq!(size_4kb_4, 4096, "Leaf level size should be page size");

    // 测试16KB页面的地址计算
    let index_16kb_1 = PageTable::<TestTable16KB, StdTestAllocator>::virt_to_index(vaddr, 1);
    let index_16kb_3 = PageTable::<TestTable16KB, StdTestAllocator>::virt_to_index(vaddr, 3);
    let size_16kb_3 = PageTable::<TestTable16KB, StdTestAllocator>::level_size(3);

    assert!(index_16kb_1 < 512, "Index should be within page table bounds");
    assert!(index_16kb_3 < 512, "Index should be within page table bounds");
    assert_eq!(size_16kb_3, 16384, "Leaf level size should be page size");

    println!("✅ 地址计算测试通过");
}

#[test]
fn test_std_alignment_checks() {
    println!("🧪 运行标准环境对齐检查测试...");

    let vaddr_aligned = VirtAddr::new(0x100000); // 1MB对齐
    let vaddr_unaligned = VirtAddr::new(0x100001);
    let paddr_aligned = PhysAddr::new(0x200000); // 1MB对齐
    let paddr_unaligned = PhysAddr::new(0x200001);

    // 测试1MB级别对齐
    assert!(PageTable::<TestTable4KB, StdTestAllocator>::is_vaddr_aligned(vaddr_aligned, 0x100000, 2));
    assert!(!PageTable::<TestTable4KB, StdTestAllocator>::is_vaddr_aligned(vaddr_unaligned, 0x100000, 2));
    assert!(PageTable::<TestTable4KB, StdTestAllocator>::is_paddr_aligned(paddr_aligned, 0x100000, 2));
    assert!(!PageTable::<TestTable4KB, StdTestAllocator>::is_paddr_aligned(paddr_unaligned, 0x100000, 2));

    println!("✅ 对齐检查测试通过");
}

#[test]
fn test_std_debug_implementations() {
    println!("🧪 运行标准环境Debug实现测试...");

    let allocator = StdTestAllocator::new();
    let page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    let config = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);

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

    println!("✅ Debug实现测试通过");
}

#[test]
fn test_std_allocator_behavior() {
    println!("🧪 运行标准环境分配器行为测试...");

    let allocator = StdTestAllocator::new();
    let mut page_table = PageTable::<TestTable4KB, _>::new(allocator)
        .expect("Failed to create page table");

    // 映射几个页面
    let config1 = create_basic_4kb_config(0x1000000, 0x2000000, 0x1000);
    let result1 = page_table.map(&config1);
    assert!(result1.is_ok(), "First mapping should succeed");

    let config2 = create_basic_4kb_config(0x1001000, 0x2001000, 0x1000);
    let result2 = page_table.map(&config2);
    assert!(result2.is_ok(), "Second mapping should succeed");

    println!("✅ 分配器行为测试通过，分配器成功处理了多个映射请求");
}
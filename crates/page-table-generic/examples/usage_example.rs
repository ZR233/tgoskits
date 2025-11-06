//! 页表映射使用示例
//!
//! 这个示例展示了如何使用page-table-generic库来创建不同架构的页表映射

#![no_std]

use page_table_generic::*;

// 简单的内存分配器实现
#[derive(Debug, Clone, Copy)]
struct SimpleAllocator {
    next_addr: usize,
}

impl SimpleAllocator {
    fn new() -> Self {
        Self { next_addr: 0x1000000 }
    }
}

impl Clone for SimpleAllocator {
    fn clone(&self) -> Self {
        Self { next_addr: self.next_addr }
    }
}

impl Copy for SimpleAllocator {}

impl FramAllocator for SimpleAllocator {
    fn alloc_frame(&self) -> Option<PhysAddr> {
        Some(PhysAddr::new(self.next_addr))
    }

    fn dealloc_frame(&self, _frame: PhysAddr) {
        // 简单实现，不进行释放
    }

    fn phys_to_virt(&self, paddr: PhysAddr) -> *mut u8 {
        paddr.raw() as *mut u8
    }
}

fn main() {
    // 创建一个x86_64架构的页表
    let allocator = SimpleAllocator::new();
    let mut page_table = PageTable::<examples::X86_64Table, _>::new(allocator)
        .expect("Failed to create page table");

    // 配置映射
    let config = MapConfig {
        vaddr: VirtAddr::new(0x1000000),
        paddr: PhysAddr::new(0x2000000),
        size: 4096, // 4KB
        pte: MockPte::new(),
        allow_huge: true,
        flush: false,
    };

    // 执行映射
    match page_table.map(&config) {
        Ok(()) => println!("✅ 页表映射成功"),
        Err(e) => println!("❌ 页表映射失败: {:?}", e),
    }

    // 测试地址计算
    let vaddr = VirtAddr::new(0x123456789ABCDEF0);
    let index = examples::X86_64Table::virt_to_index(vaddr, 1);
    let level_size = examples::X86_64Table::level_size(1);

    println!("虚拟地址 {:#x} 在第1级的索引: {}", vaddr.raw(), index);
    println!("第1级对应的映射大小: {:#x} bytes", level_size);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_different_architectures() {
        // 测试x86_64架构
        let allocator = SimpleAllocator::new();
        let x86_64_table: PageTable<examples::X86_64Table, _> =
            PageTable::new(allocator).expect("Failed to create x86_64 table");
        println!("✅ x86_64页表创建成功");

        // 测试ARM64架构
        let allocator = SimpleAllocator::new();
        let arm64_table: PageTable<examples::ARM64Table, _> =
            PageTable::new(allocator).expect("Failed to create ARM64 table");
        println!("✅ ARM64页表创建成功");

        // 测试RISC-V架构
        let allocator = SimpleAllocator::new();
        let riscv_table: PageTable<examples::RISCV64Table, _> =
            PageTable::new(allocator).expect("Failed to create RISC-V table");
        println!("✅ RISC-V页表创建成功");
    }

    #[test]
    fn test_address_calculations() {
        let vaddr = VirtAddr::new(0x123456789ABCDEF0);

        // 测试4KB页面配置
        let index_x86_1 = examples::X86_64Table::virt_to_index(vaddr, 1);
        let index_x86_4 = examples::X86_64Table::virt_to_index(vaddr, 4);
        assert!(index_x86_1 < 512);
        assert!(index_x86_4 < 512);

        // 测试16KB页面配置
        let index_arm16_1 = examples::ARM64LargeTable::virt_to_index(vaddr, 1);
        let index_arm16_3 = examples::ARM64LargeTable::virt_to_index(vaddr, 3);
        assert!(index_arm16_1 < 512);
        assert!(index_arm16_3 < 512);

        println!("✅ 地址计算测试通过");
    }

    #[test]
    fn test_page_sizes() {
        assert_eq!(examples::X86_64Table::PAGE_SIZE, 4096);
        assert_eq!(examples::X86_64Table::LEVEL, 4);

        assert_eq!(examples::ARM64LargeTable::PAGE_SIZE, 16384);
        assert_eq!(examples::ARM64LargeTable::LEVEL, 3);

        assert_eq!(examples::LargePageTable::PAGE_SIZE, 65536);
        assert_eq!(examples::LargePageTable::LEVEL, 3);

        println!("✅ 页面大小配置测试通过");
    }
}
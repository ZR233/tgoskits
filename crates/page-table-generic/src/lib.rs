#![no_std]

use core::fmt::Debug;

mod def;
pub mod frame;
mod map;
mod table;
mod walk;

pub use def::*;
pub use frame::Frame;
pub use map::*;
pub use table::*;
pub use walk::*;

pub type PagingResult<T = ()> = Result<T, PagingError>;

pub trait FrameAllocator: Clone + Sync + Send + 'static {
    fn alloc_frame(&self) -> Option<PhysAddr>;

    fn dealloc_frame(&self, frame: PhysAddr);

    fn phys_to_virt(&self, paddr: PhysAddr) -> *mut u8;
}

pub trait TableGeneric: Sync + Send + Clone + Copy + 'static {
    type P: PageTableEntry;

    /// 页面大小（支持4KB、16KB、64KB等）
    const PAGE_SIZE: usize;

    /// 各级索引位数数组，从最高级到最低级
    const LEVEL_BITS: &[usize];

    /// 大页最高支持的级别
    const MAX_BLOCK_LEVEL: usize;

    /// 刷新TLB
    fn flush(vaddr: Option<VirtAddr>);
}

pub trait PageTableEntry: Debug + Sync + Send + Clone + Copy + Sized + 'static {
    fn new_valid() -> Self;

    fn valid(&self) -> bool;
    fn set_valid(&mut self, valid: bool);

    fn paddr(&self) -> PhysAddr;
    fn set_paddr(&mut self, paddr: PhysAddr);

    /// 检查是否为大页映射
    ///
    /// # 参数
    /// - `is_dir`: 是否为目录项（只有目录项才能是大页）
    fn is_huge(&self, is_dir: bool) -> bool;
    /// 设置大页标志
    ///
    /// # 参数
    /// - `is_dir`: 是否为目录项
    fn set_is_huge(&mut self, b: bool, is_dir: bool);

    fn is_writable(&self) -> bool;
    fn set_writable(&mut self, b: bool);

    fn is_executable(&self) -> bool;
    fn set_executable(&mut self, b: bool);

    fn is_lower_access(&self) -> bool;
    fn set_lower_access(&mut self, b: bool);

    /// 检查是否为全局映射
    ///
    /// # 参数
    /// - `is_dir`: 是否为目录项（PMD/PUD/PGD）
    fn is_global(&self, is_dir: bool) -> bool;
    /// 设置全局映射标志
    ///
    /// # 参数
    /// - `is_dir`: 是否为目录项
    fn set_global(&mut self, b: bool, is_dir: bool);

    fn is_accessed(&self) -> bool;
    fn set_accessed(&mut self, b: bool);

    fn is_dirty(&self) -> bool;
    fn set_dirty(&mut self, b: bool);

    fn mem_attr(&self) -> MemAttributes;
    fn set_mem_attr(&mut self, attr: MemAttributes);
}

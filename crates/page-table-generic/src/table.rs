use crate::{
    FramAllocator, PageTableEntry, PagingError, PagingResult, PhysAddr, TableGeneric, VirtAddr,
};

/// 页表映射配置
#[repr(C)]
#[derive(Clone, Copy)]
pub struct MapConfig<P: PageTableEntry> {
    pub vaddr: VirtAddr,
    pub paddr: PhysAddr,
    pub size: usize,
    /// Page Table Entry
    ///
    /// All pte will be set as this value, except the address bits
    pub pte: P,
    pub allow_huge: bool,
    pub flush: bool,
}

impl<P: PageTableEntry> core::fmt::Debug for MapConfig<P> {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("MapConfig")
            .field("vaddr", &format_args!("{:#x}", self.vaddr.raw()))
            .field("paddr", &format_args!("{:#x}", self.paddr.raw()))
            .field("size", &format_args!("{:#x}", self.size))
            .field("allow_huge", &self.allow_huge)
            .field("flush", &self.flush)
            .finish()
    }
}

// 常量优化：页表索引位数为9（512个条目）
// 这个值在大多数架构中是标准的
pub(crate) const PAGE_INDEX_BITS: usize = 9;
pub(crate) const PAGE_INDEX_MASK: usize = (1 << PAGE_INDEX_BITS) - 1; // 511

/// 页表结构
pub struct PageTable<T: TableGeneric, A: FramAllocator> {
    root: Frame<T, A>,
}

impl<T: TableGeneric, A: FramAllocator> core::fmt::Debug for PageTable<T, A>
where
    T::P: core::fmt::Debug,
{
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("PageTable")
            .field("root_paddr", &format_args!("{:#x}", self.root.paddr.raw()))
            .field("table_levels", &T::LEVEL)
            .field("max_block_level", &T::MAX_BLOCK_LEVEL)
            .field("page_size", &format_args!("{:#x}", T::PAGE_SIZE))
            .finish()
    }
}

impl<T: TableGeneric, A: FramAllocator> PageTable<T, A> {
    /// 创建一个新的页表
    pub fn new(allocator: A) -> PagingResult<Self> {
        let root = Frame::new(allocator)?;
        Ok(Self { root })
    }

    /// 映射虚拟地址范围到物理地址范围
    pub fn map(&mut self, config: &MapConfig<T::P>) -> PagingResult {
        // 验证输入参数
        self.validate_map_config(config)?;

        // 检查大小溢出
        if config.vaddr.raw().checked_add(config.size).is_none() ||
           config.paddr.raw().checked_add(config.size).is_none() {
            return Err(PagingError::address_overflow("Virtual or physical address overflow"));
        }

        let mut vaddr = config.vaddr;
        let mut paddr = config.paddr;
        let mut size = config.size;
        let mut mapped_total = 0;

        // 创建根页表的临时借用，然后在循环中释放
        while size > 0 {
            // 将root的paddr和allocator提取出来
            let root_paddr = self.root.paddr;
            let allocator = self.root.allocator;

            // 在这里调用一个新的映射函数，它不使用self的可变借用
            let mapped_size = Self::map_range_no_self(
                root_paddr,
                allocator,
                vaddr,
                paddr,
                size,
                T::LEVEL,
                config,
            )?;

            // 更新进度
            vaddr += mapped_size;
            paddr += mapped_size;
            size -= mapped_size;
            mapped_total += mapped_size;

            // 防止无限循环
            if mapped_size == 0 {
                return Err(PagingError::invalid_size("Zero mapping size detected"));
            }
        }

        // 验证映射大小
        if mapped_total != config.size {
            return Err(PagingError::invalid_size("Mapping size mismatch"));
        }

        if config.flush {
            T::flush(Some(config.vaddr));
        }

        Ok(())
    }

    /// 验证映射配置的有效性
    fn validate_map_config(&self, config: &MapConfig<T::P>) -> PagingResult {
        if config.size == 0 {
            return Err(PagingError::invalid_size("Size cannot be zero"));
        }

        // 检查虚拟地址和物理地址是否页对齐
        if config.vaddr.raw() % T::PAGE_SIZE != 0 {
            return Err(PagingError::alignment_error("Virtual address not page aligned"));
        }

        if config.paddr.raw() % T::PAGE_SIZE != 0 {
            return Err(PagingError::alignment_error("Physical address not page aligned"));
        }

        Ok(())
    }

    /// 计算指定级别的页表索引（通用版本）
    pub fn virt_to_index(vaddr: VirtAddr, level: usize) -> usize {
        if level == 0 || level > T::LEVEL {
            panic!("Invalid level: {} (valid: 1..{})", level, T::LEVEL);
        }
        // 计算当前级别的位移：页面大小的对数 + (总级别 - 当前级别) * 索引位数
        let page_shift = T::PAGE_SIZE.trailing_zeros() as usize;
        let shift = page_shift + (T::LEVEL - level) * PAGE_INDEX_BITS;
        (vaddr.raw() >> shift) & PAGE_INDEX_MASK
    }

    /// 计算指定级别对应的映射大小（通用版本）
    pub fn level_size(level: usize) -> usize {
        if level == T::LEVEL {
            // 最后一级是页级别
            T::PAGE_SIZE
        } else if level > T::MAX_BLOCK_LEVEL {
            // 不支持大页的级别
            T::PAGE_SIZE
        } else {
            // 大页级别：页面大小 * 2^(索引位数 * (总级别 - 当前级别))
            T::PAGE_SIZE << (PAGE_INDEX_BITS * (T::LEVEL - level))
        }
    }

    /// 检查虚拟地址在指定级别是否对齐
    pub fn is_vaddr_aligned(vaddr: VirtAddr, size: usize, level: usize) -> bool {
        let level_size = Self::level_size(level);
        vaddr.raw() % level_size == 0 && size % level_size == 0
    }

    /// 检查物理地址在指定级别是否对齐
    pub fn is_paddr_aligned(paddr: PhysAddr, size: usize, level: usize) -> bool {
        let level_size = Self::level_size(level);
        paddr.raw() % level_size == 0 && size % level_size == 0
    }

    /// 计算在指定级别可以映射的最大范围
    #[allow(dead_code)]
    fn calc_mapping_range(vaddr: VirtAddr, size: usize, level: usize) -> usize {
        let level_size = Self::level_size(level);

        // 计算到下一个级别边界的偏移
        let offset_to_boundary = level_size - (vaddr.raw() % level_size);

        // 如果剩余大小不足以到达边界，使用剩余大小
        if size <= offset_to_boundary {
            // 使用可能的最大对齐大小
            let mut current_level = level;
            while current_level > 1 && Self::is_vaddr_aligned(vaddr, size, current_level - 1) {
                current_level -= 1;
            }
            return Self::level_size(current_level);
        }

        level_size
    }

    /// 检查是否应该使用大页映射
    fn should_use_huge_page(
        vaddr: VirtAddr,
        paddr: PhysAddr,
        size: usize,
        level: usize,
        config: &MapConfig<T::P>,
    ) -> bool {
        // 如果配置不允许大页，直接返回false
        if !config.allow_huge {
            return false;
        }

        // 只能在支持大页的级别使用大页
        if level > T::MAX_BLOCK_LEVEL {
            return false;
        }

        // 检查地址对齐
        Self::is_vaddr_aligned(vaddr, size, level) && Self::is_paddr_aligned(paddr, size, level)
    }

    /// 找到最优的映射级别
    fn find_optimal_level(
        vaddr: VirtAddr,
        paddr: PhysAddr,
        size: usize,
        config: &MapConfig<T::P>,
    ) -> usize {
        // 从最高的大页级别开始检查
        for level in 1..=T::MAX_BLOCK_LEVEL {
            if Self::should_use_huge_page(vaddr, paddr, size, level, config) {
                return level;
            }
        }

        // 如果不能使用大页，返回页表级别（LEVEL）
        T::LEVEL
    }

    /// 简化的映射函数，避免借用检查器问题
    fn map_range_no_self(
        root_paddr: PhysAddr,
        allocator: A,
        vaddr: VirtAddr,
        paddr: PhysAddr,
        size: usize,
        level: usize,
        config: &MapConfig<T::P>,
    ) -> PagingResult<usize> {
        // 创建frame并递归映射
        let mut frame = Frame {
            paddr: root_paddr,
            allocator,
            _marker: core::marker::PhantomData,
        };

        Self::map_range_recursive(&mut frame, vaddr, paddr, size, level, config)
    }

    /// 递归映射的核心实现
    fn map_range_recursive(
        frame: &mut Frame<T, A>,
        vaddr: VirtAddr,
        paddr: PhysAddr,
        size: usize,
        level: usize,
        config: &MapConfig<T::P>,
    ) -> PagingResult<usize> {
        // 找到最优的映射级别
        let optimal_level = Self::find_optimal_level(vaddr, paddr, size, config);

        // 如果当前级别可以使用大页且级别匹配
        if optimal_level <= T::MAX_BLOCK_LEVEL && level == optimal_level {
            let level_size = Self::level_size(level);

            // 确保我们不会映射超过请求的大小
            let actual_size = size.min(level_size);

            // 创建大页映射
            Self::map_huge_page_static(frame, vaddr, paddr, actual_size, level, config)?;

            return Ok(actual_size);
        }

        // 如果到达页表级别，进行普通页映射
        if level == 1 {
            let index = Self::virt_to_index(vaddr, level);
            let entries = frame.as_slice_mut();

            // 检查是否已经映射
            let entry = &mut entries[index];
            if entry.valid() {
                return Err(PagingError::mapping_conflict(vaddr, entry.paddr()));
            }

            // 创建页表项
            Self::create_page_table_entry_static(entry, paddr, config);
            return Ok(T::PAGE_SIZE);
        }

        // 否则，递归到下一级别
        Self::map_next_level_static(frame, vaddr, paddr, size, level, config)
    }

    /// 映射大页
    fn map_huge_page_static(
        frame: &mut Frame<T, A>,
        vaddr: VirtAddr,
        paddr: PhysAddr,
        _size: usize,
        level: usize,
        config: &MapConfig<T::P>,
    ) -> PagingResult {
        let index = Self::virt_to_index(vaddr, level);
        let entry = &mut frame.as_slice_mut()[index];

        if entry.valid() {
            return Err(PagingError::mapping_conflict(vaddr, entry.paddr()));
        }

        // 创建大页映射
        let mut pte = config.pte;
        pte.set_paddr(paddr);
        pte.set_valid(true);
        pte.set_is_huge(true);

        *entry = pte;

        Ok(())
    }

    /// 映射到下一级别
    fn map_next_level_static(
        frame: &mut Frame<T, A>,
        vaddr: VirtAddr,
        paddr: PhysAddr,
        _size: usize,
        level: usize,
        config: &MapConfig<T::P>,
    ) -> PagingResult<usize> {
        // 获取当前级别的索引
        let index = Self::virt_to_index(vaddr, level);
        let allocator = frame.allocator;

        // 检查或创建子页表
        let mut child_frame = {
            let entries = frame.as_slice_mut();

            if entries[index].valid() {
                if entries[index].is_huge() {
                    return Err(PagingError::hierarchy_error("Cannot create page table under huge page"));
                }

                // 子页表已存在，获取它
                Frame {
                    paddr: entries[index].paddr(),
                    allocator,
                    _marker: core::marker::PhantomData,
                }
            } else {
                // 需要创建新的子页表
                let new_frame = Frame::new(allocator)?;

                // 链接子页表
                let mut pte = config.pte;
                pte.set_paddr(new_frame.paddr);
                pte.set_valid(true);
                pte.set_is_huge(false);

                entries[index] = pte;

                new_frame
            }
        };

        // 递归映射
        let mapped_size = Self::map_range_recursive(&mut child_frame, vaddr, paddr, T::PAGE_SIZE, level - 1, config)?;

        Ok(mapped_size)
    }

    /// 创建页表项
    fn create_page_table_entry_static(entry: &mut T::P, paddr: PhysAddr, config: &MapConfig<T::P>) {
        let mut pte = config.pte;
        pte.set_paddr(paddr);
        pte.set_valid(true);
        pte.set_is_huge(false);
        *entry = pte;
    }
}

struct Frame<T: TableGeneric, A: FramAllocator> {
    paddr: PhysAddr,
    allocator: A,
    _marker: core::marker::PhantomData<T>,
}

impl<T: TableGeneric, A: FramAllocator> core::fmt::Debug for Frame<T, A> {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Frame")
            .field("paddr", &format_args!("{:#x}", self.paddr.raw()))
            .finish()
    }
}

impl<T, A> Frame<T, A>
where
    T: TableGeneric,
    A: FramAllocator,
{
    fn new(allocator: A) -> PagingResult<Self> {
        let paddr = allocator.alloc_frame().ok_or(PagingError::NoMemory)?;
        unsafe {
            let vaddr = allocator.phys_to_virt(paddr);
            core::ptr::write_bytes(vaddr, 0, T::PAGE_SIZE);
        }

        Ok(Self {
            paddr,
            allocator,
            _marker: core::marker::PhantomData,
        })
    }

    fn as_slice_mut(&mut self) -> &mut [T::P] {
        let vaddr = self.allocator.phys_to_virt(self.paddr);
        unsafe { core::slice::from_raw_parts_mut(vaddr as *mut T::P, T::TABLE_LEN) }
    }

    #[allow(dead_code)]
    fn as_slice(&self) -> &[T::P] {
        let vaddr = self.allocator.phys_to_virt(self.paddr);
        unsafe { core::slice::from_raw_parts(vaddr as *const T::P, T::TABLE_LEN) }
    }
}

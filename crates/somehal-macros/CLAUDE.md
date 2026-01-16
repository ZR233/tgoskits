[根目录](../../CLAUDE.md) > [crates](../) > **someboot-macros**

# SomeHAL Macros - 硬件抽象层宏定义库

## 模块职责

SomeHAL Macros 为 SomeHAL 硬件抽象层提供专用的过程宏，简化架构特定代码的编写，生成统一的接口实现，并提供编译时的架构验证和代码优化。

## 入口与启动

### 主要入口点
- **`src/lib.rs`**: 库入口，导出所有宏
- **核心宏**:
  - `entry` - 架构入口点标记
  - 其他架构相关的辅助宏

## 对外接口

### 入口点宏 (`entry.rs`)
```rust
use someboot_macros::entry;

#[entry]
pub unsafe extern "C" fn kernel_entry(
    fdt_addr: usize,
) -> ! {
    // 架构特定的初始化代码

    // 调用通用的内核入口
    kernel_main(fdt_addr)
}
```

功能：
- 设置正确的调用约定
- 处理架构特定的属性
- 确保入口点符合硬件要求
- 生成必要的启动样板代码

## 关键依赖与配置

### 核心依赖
```toml
[dependencies]
syn = {version = "2.0", features = ["full"]}  # 完整的 AST 解析
quote = "1.0"                                 # 代码生成
proc-macro2 = "1.0"                           # 过程宏支持
```

### 构建依赖
```toml
[build-dependencies]
prettyplease = "0.2"  # 代码格式化
quote = "1.0"         # 代码生成
syn = "2.0"           # AST 处理
```

## 宏实现细节

### Entry 宏实现

#### 1. 属性处理
宏会自动添加以下属性：
- `#[no_mangle]`: 防止名称修饰
- `#[naked]`: 如果需要裸函数
- 特定的链接段属性
- 对齐要求

#### 2. 函数签名验证
- 确保函数是 `unsafe extern "C"`
- 验证返回类型是 `!`（永不返回）
- 检查参数数量和类型

#### 3. 栶构特定代码生成
根据目标架构生成：
- AArch64: 设置 EL 异常级别
- LoongArch64: 配置直接映射窗口
- x86_64: 设置页表和段

### 构建时宏处理

#### 构建脚本逻辑
在 `build.rs` 中：
1. 解析源代码中的宏使用
2. 生成架构特定的代码
3. 处理条件编译
4. 格式化生成的代码

## 使用场景

### AArch64 内核入口
```rust
use someboot_macros::entry;

#[entry]
pub unsafe extern "C" fn kernel_entry(
    fdt_addr: usize,
) -> ! {
    // 清零 BSS
    zero_bss();

    // 设置栈
    setup_stack();

    // 初始化 MMU
    init_mmu();

    // 进入 Rust 代码
    kernel_main(fdt_addr)
}
```

### LoongArch64 内核入口
```rust
use someboot_macros::entry;

#[entry]
pub unsafe extern "C" fn kernel_entry(
    efi_boot: usize,
    cmdline: *const u8,
    systemtable: *const c_void,
) -> ! {
    // 设置直接映射窗口
    setup_direct_map();

    // 初始化页表
    init_page_table();

    // 启用 MMU
    enable_mmu();

    // 跳转到虚拟地址
    jump_to_virt();

    // 进入主函数
    kernel_main(efi_boot, cmdline, systemtable)
}
```

## 架构支持

### 当前支持的架构
1. **AArch64 (ARMv8)**
   - EL1/EL2 异常级别
   - 页表管理
   - 异常向量设置

2. **LoongArch64**
   - 直接映射窗口
   - CSR 寄存器操作
   - TLB 管理

3. **x86_64 (部分)**
   - 基础启动支持
   - 长模式切换

### 架构检测
宏会自动检测目标架构：
```rust
#[cfg(target_arch = "aarch64")]
// AArch64 特定代码

#[cfg(target_arch = "loongarch64")]
// LoongArch64 特定代码
```

## 测试与质量

### 当前测试状态
- ❌ **单元测试**: 缺少正式的单元测试
- ⚠️ **集成测试**: 依赖实际硬件测试
- ⚠️ **编译测试**: 通过实际使用验证

### 建议的测试策略
1. **宏展开测试**: 验证宏生成的代码
2. **多架构测试**: 在支持的架构上验证
3. **边界测试**: 测试各种参数组合
4. **错误处理测试**: 验证错误消息的质量

## 宏设计原则

### 架构无关性
- 使用条件编译处理架构差异
- 提供统一的接口
- 避免架构特定的硬编码

### 性能考虑
- 零运行时开销
- 编译时优化
- 最小化代码生成

### 安全性
- 防止未定义行为
- 维护类型安全
- 正确的内存模型

## 最佳实践

### 使用建议
1. **保持简单**
   - 宏应该做一件事情并做好
   - 避免过度复杂的逻辑

2. **清晰的错误消息**
   - 提供有用的编译错误
   - 指出问题所在和解决方法

3. **文档齐全**
   - 解释宏的用途
   - 提供使用示例
   - 说明注意事项

### 维护指南
1. **版本兼容性**
   - 保持向后兼容
   - 使用语义化版本
   - 记录破坏性变更

2. **代码质量**
   - 遵循 Rust 编码规范
   - 保持代码简洁
   - 添加适当注释

## 常见问题 (FAQ)

### Q: 为什么需要架构特定的入口宏？
A: 不同架构有不同的启动要求，如异常级别、页表设置、寄存器配置等。宏确保这些要求得到满足。

### Q: 可以在其他项目中使用这些宏吗？
A: 这些宏专为 SomeHAL 设计，但可以作为参考或基础在其他类似项目中使用。

### Q: 如何添加新架构支持？
A: 需要在宏中添加新架构的条件编译分支，实现架构特定的代码生成逻辑。

### Q: 宏生成的代码是否可调试？
A: 是的，生成的代码包含适当的调试信息，可以像普通代码一样调试。

## 相关文件清单

### 核心文件
- `src/lib.rs` - 库入口和宏导出
- `src/entry.rs` - 入口点宏实现
- `build.rs` - 构建脚本，处理代码生成

### 配置文件
- `Cargo.toml` - 项目配置

### 生成文件（build 时）
- 可能生成的架构特定代码文件

---

## 变更记录 (Changelog)

### 2025-12-21 21:10:20
- 初始化 someboot-macros 模块文档
- 完成核心宏分析和使用示例
- 识别架构支持和测试策略
- 建立维护指南和常见问题解答
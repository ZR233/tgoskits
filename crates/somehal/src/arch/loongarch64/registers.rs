//! LoongArch64 寄存器位域定义模块
//!
//! 使用 tock-registers 风格定义控制寄存器布局
//! 参考: LoongArch64 参考手册

use tock_registers::register_bitfields;

// LoongArch64 控制寄存器位域定义
register_bitfields![u64,
    /// PWCTL0 寄存器 - 页表遍历控制寄存器 0
    PWCTL0 [
        /// PTBASE - 页表基址 (bits 4-0)
        PTBASE OFFSET(0) NUMBITS(5) [],

        /// PTWIDTH - 页表宽度 (bits 9-5)
        PTWIDTH OFFSET(5) NUMBITS(5) [],

        /// DIR0BASE - 目录0基址 (bits 14-10)
        DIR0BASE OFFSET(10) NUMBITS(5) [],

        /// DIR0WIDTH - 目录0宽度 (bits 19-15)
        DIR0WIDTH OFFSET(15) NUMBITS(5) [],

        /// DIR1BASE - 目录1基址 (bits 24-20)
        DIR1BASE OFFSET(20) NUMBITS(5) [],

        /// DIR1WIDTH - 目录1宽度 (bits 29-25)
        DIR1WIDTH OFFSET(25) NUMBITS(5) [],

        /// DIR2WIDTH - 目录2宽度 (bits 34-30)
        DIR2WIDTH OFFSET(30) NUMBITS(5) [],

        /// PTEW - 页表项宽度 (bits 31-30)
        PTEW OFFSET(30) NUMBITS(2) [],
    ],

    /// PWCTL1 寄存器 - 页表遍历控制寄存器 1
    PWCTL1 [
        /// DIR2BASE - 目录2基址 (bits 5-0)
        DIR2BASE OFFSET(0) NUMBITS(6) [],

        /// DIR2WIDTH - 目录2宽度 (bits 11-6)
        DIR2WIDTH OFFSET(6) NUMBITS(6) [],

        /// DIR3BASE - 目录3基址 (bits 17-12)
        DIR3BASE OFFSET(12) NUMBITS(6) [],

        /// DIR3WIDTH - 目录3宽度 (bits 23-18)
        DIR3WIDTH OFFSET(18) NUMBITS(6) [],

        /// PTW - 硬件页表遍历使能 (bit 24)
        PTW OFFSET(24) NUMBITS(1) [],
    ],

    /// TLBIDX 寄存器 - TLB 索引寄存器
    TLBIDX [
        /// INDEX - TLB 索引 (bits 11-0)
        INDEX OFFSET(0) NUMBITS(12) [],

        /// PS - 页大小 (bits 29-24)
        PS OFFSET(24) NUMBITS(6) [],
    ],

    /// TLBREHI 寄存器 - TLB Refill Entry High
    TLBREHI [
        /// PS - TLB Refill 页大小 (bits 5-0)
        PS OFFSET(0) NUMBITS(6) [],
    ],
];

/// 生成 ADRP + ADD 指令组合，用于加载符号地址
/// ADRP 计算页面基地址，ADD 加上页内偏移
macro_rules! sym_addr {
    ($reg:ident, $symbol:expr) => {
        concat!(
            "adrp ",
            stringify!($reg),
            ", ",
            $symbol,
            "\n",
            "add ",
            stringify!($reg),
            ", ",
            stringify!($reg),
            ", :lo12:",
            $symbol
        )
    };
}

use core::ptr::NonNull;

use crate::Error;

pub const EPHY_TOP_WRAP_BASE: usize = 0x0300_9800;
pub const EPHY_BASE: usize = 0x0300_9000;
pub const EPHY_TOP_WRAP_SIZE: usize = 0x8;
pub const EPHY_ANALOG_SIZE: usize = 0x80;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EphyMmio {
    pub top_wrap: NonNull<u8>,
    pub analog: NonNull<u8>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EphyTuning {
    pub txitune: u16,
    pub txechoi: u16,
    pub txrterm_echo: u16,
}

impl Default for EphyTuning {
    fn default() -> Self {
        Self {
            txitune: 0x5a5a,
            txechoi: 0x0000,
            txrterm_echo: 0x0bb0,
        }
    }
}

pub fn fallback_init_sequence(tuning: EphyTuning) -> &'static [(usize, u16)] {
    // Kept for unit-test visibility; the runtime function below writes the
    // same sequence directly so no heap allocation is needed.
    let _ = tuning;
    FALLBACK_SEQUENCE
}

const FALLBACK_SEQUENCE: &[(usize, u16)] = &[
    (0x7c, 0x0000),
    (0x5c, 0x0c10),
    (0x68, 0x0003),
    (0x54, 0x0000),
    (0x7c, 0x1000),
    (0x68, 0x1000),
    (0x6c, 0x3020),
    (0x70, 0x5040),
    (0x74, 0x7060),
    (0x58, 0x1708),
    (0x5c, 0x3827),
    (0x60, 0x5748),
    (0x64, 0x7867),
    (0x7c, 0x1100),
    (0x40, 0x9080),
    (0x44, 0xb0a0),
    (0x48, 0xd0c0),
    (0x4c, 0xf0e0),
    (0x50, 0x9788),
    (0x54, 0xb8a7),
    (0x58, 0xd7c8),
    (0x5c, 0xf8e7),
    (0x7c, 0x0500),
    (0x7c, 0x0a00),
    (0x40, 0x3e00),
    (0x44, 0x7864),
    (0x48, 0x6470),
    (0x4c, 0x5f62),
    (0x50, 0x5a5a),
    (0x54, 0x5458),
    (0x58, 0xb23a),
    (0x5c, 0x94a0),
    (0x60, 0x9092),
    (0x64, 0x8a8e),
    (0x68, 0x8688),
    (0x6c, 0x8484),
    (0x70, 0x0082),
    (0x7c, 0x0b00),
    (0x40, 0x5252),
    (0x44, 0x5252),
    (0x48, 0x4b52),
    (0x4c, 0x3d47),
    (0x50, 0xaa99),
    (0x54, 0x989e),
    (0x58, 0x9395),
    (0x5c, 0x9091),
    (0x60, 0x8e8f),
    (0x64, 0x8d8e),
    (0x68, 0x8c8c),
    (0x6c, 0x8b8b),
    (0x70, 0x008a),
    (0x7c, 0x0d00),
    (0x40, 0x1e0a),
    (0x44, 0x3862),
    (0x48, 0x1e62),
    (0x4c, 0x2a08),
    (0x50, 0x244c),
    (0x54, 0x1a44),
    (0x58, 0x061c),
    (0x7c, 0x0e00),
    (0x40, 0x2d30),
    (0x44, 0x3470),
    (0x48, 0x0648),
    (0x4c, 0x261c),
    (0x50, 0x3160),
    (0x54, 0x2d5e),
    (0x7c, 0x0f00),
    (0x40, 0x2922),
    (0x44, 0x366e),
    (0x48, 0x0752),
    (0x4c, 0x2556),
    (0x50, 0x2348),
    (0x54, 0x0c30),
    (0x7c, 0x1000),
    (0x40, 0x1e08),
    (0x44, 0x3868),
    (0x48, 0x1462),
    (0x4c, 0x1a0e),
    (0x50, 0x305e),
    (0x54, 0x2f62),
    (0x7c, 0x0100),
    (0x7c, 0x1300),
    (0x58, 0x0012),
    (0x5c, 0x6848),
    (0x7c, 0x1200),
    (0x48, 0x0808),
    (0x4c, 0x0808),
    (0x50, 0x32f8),
    (0x54, 0xf8dc),
    (0x7c, 0x0000),
];

pub fn init(mmio: EphyMmio, tuning: EphyTuning) -> Result<(), Error> {
    write16(mmio.top_wrap, 0x04, 0x0001);
    clear16(mmio.analog, 0x00, 0x0003);
    reset_settle_delay();
    write16(mmio.analog, 0x7c, 0x0000);
    write16(mmio.analog, 0x64, tuning.txitune);
    write16(mmio.analog, 0x54, tuning.txechoi);
    write16(mmio.analog, 0x58, tuning.txrterm_echo);

    for &(offset, value) in FALLBACK_SEQUENCE {
        write16(mmio.analog, offset, value);
        if offset == 0x7c && value == 0x0500 {
            set16(mmio.analog, 0x40, 0x0001);
            set16(mmio.analog, 0x4c, 0x0820);
        }
        if offset == 0x7c && value == 0x0100 {
            clear16(mmio.analog, 0x68, 0x0f00);
        }
    }

    write16(mmio.top_wrap, 0x00, 0x090e);
    set16(mmio.analog, 0x00, 0x0100);
    write16(mmio.top_wrap, 0x04, 0x0000);
    Ok(())
}

fn reset_settle_delay() {
    for _ in 0..200_000 {
        core::hint::spin_loop();
    }
}

fn write16(base: NonNull<u8>, offset: usize, value: u16) {
    unsafe {
        base.as_ptr()
            .add(offset)
            .cast::<u32>()
            .write_volatile(u32::from(value));
    }
}

fn set16(base: NonNull<u8>, offset: usize, bits: u16) {
    unsafe {
        let ptr = base.as_ptr().add(offset).cast::<u32>();
        let value = ptr.read_volatile() | u32::from(bits);
        ptr.write_volatile(value);
    }
}

fn clear16(base: NonNull<u8>, offset: usize, bits: u16) {
    unsafe {
        let ptr = base.as_ptr().add(offset).cast::<u32>();
        let value = ptr.read_volatile() & !u32::from(bits);
        ptr.write_volatile(value);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fallback_sequence_contains_final_page0_restore() {
        let seq = fallback_init_sequence(EphyTuning::default());
        assert!(seq.len() > 80);
        assert_eq!(seq.last(), Some(&(0x7c, 0x0000)));
    }

    #[test]
    fn fallback_sequence_contains_sg2002_cv181x_tail_tuning() {
        let seq = fallback_init_sequence(EphyTuning::default());
        assert!(
            seq.windows(2)
                .any(|window| window == [(0x7c, 0x1300), (0x58, 0x0012)])
        );
        assert!(
            seq.windows(3)
                .any(|window| { window == [(0x7c, 0x1200), (0x48, 0x0808), (0x4c, 0x0808)] })
        );
    }
}

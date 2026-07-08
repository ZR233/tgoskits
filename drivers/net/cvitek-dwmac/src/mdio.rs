use crate::{Error, regs::Regs};

const MII_BUSY: u32 = 1;
const MII_WRITE: u32 = 1 << 1;
const MII_DATA_MASK: u32 = 0xffff;
const PHY_ADDR_SHIFT: u32 = 11;
const PHY_REG_SHIFT: u32 = 6;
const PHY_ADDR_MASK: u32 = 0x1f << PHY_ADDR_SHIFT;
const PHY_REG_MASK: u32 = 0x1f << PHY_REG_SHIFT;
const CLK_CSR_SHIFT: u32 = 2;
const CLK_CSR_MASK: u32 = 0xf << CLK_CSR_SHIFT;
const DEFAULT_CLK_CSR: u32 = 5;

#[derive(Clone, Copy)]
pub(crate) struct Mdio {
    regs: Regs,
    clk_csr: u32,
}

impl Mdio {
    pub(crate) const fn new(regs: Regs) -> Self {
        Self {
            regs,
            clk_csr: DEFAULT_CLK_CSR,
        }
    }

    pub(crate) fn read(self, phy: u8, reg: u8) -> Result<u16, Error> {
        self.wait_idle()?;
        let value = self.op_value(phy, reg, false);
        self.regs.write_mii_data(0);
        self.regs.write_mii_addr(value);
        self.wait_idle()?;
        Ok((self.regs.mii_data() & MII_DATA_MASK) as u16)
    }

    pub(crate) fn write(self, phy: u8, reg: u8, data: u16) -> Result<(), Error> {
        self.wait_idle()?;
        self.regs.write_mii_data(u32::from(data));
        self.regs.write_mii_addr(self.op_value(phy, reg, true));
        self.wait_idle()
    }

    fn op_value(self, phy: u8, reg: u8, write: bool) -> u32 {
        let mut value = MII_BUSY
            | ((u32::from(phy) << PHY_ADDR_SHIFT) & PHY_ADDR_MASK)
            | ((u32::from(reg) << PHY_REG_SHIFT) & PHY_REG_MASK)
            | ((self.clk_csr << CLK_CSR_SHIFT) & CLK_CSR_MASK);
        if write {
            value |= MII_WRITE;
        }
        value
    }

    fn wait_idle(self) -> Result<(), Error> {
        for _ in 0..10_000 {
            if self.regs.mii_addr() & MII_BUSY == 0 {
                return Ok(());
            }
            core::hint::spin_loop();
        }
        Err(Error::MdioTimeout)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mdio_op_value_uses_gmac1000_layout() {
        let regs = Regs::new(core::ptr::NonNull::dangling());
        let mdio = Mdio::new(regs);
        let value = mdio.op_value(3, 4, true);
        assert_eq!((value & PHY_ADDR_MASK) >> PHY_ADDR_SHIFT, 3);
        assert_eq!((value & PHY_REG_MASK) >> PHY_REG_SHIFT, 4);
        assert_ne!(value & MII_WRITE, 0);
        assert_ne!(value & MII_BUSY, 0);
    }
}

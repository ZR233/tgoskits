use crate::{Error, mdio::Mdio};

const MII_BMCR: u8 = 0;
const MII_BMSR: u8 = 1;
const MII_PHYSID1: u8 = 2;
const MII_PHYSID2: u8 = 3;
const MII_ADVERTISE: u8 = 4;

const BMCR_FULLDPLX: u16 = 1 << 8;
const BMCR_ANRESTART: u16 = 1 << 9;
const BMCR_ANENABLE: u16 = 1 << 12;
const BMCR_SPEED100: u16 = 1 << 13;

const BMSR_LSTATUS: u16 = 1 << 2;
const BMSR_ANEGCOMPLETE: u16 = 1 << 5;

const ADVERTISE_10HALF: u16 = 1 << 5;
const ADVERTISE_10FULL: u16 = 1 << 6;
const ADVERTISE_100HALF: u16 = 1 << 7;
const ADVERTISE_100FULL: u16 = 1 << 8;
const ADVERTISE_CSMA: u16 = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhyStatus {
    pub addr: u8,
    pub id: u32,
    pub link_up: bool,
    pub autoneg_complete: bool,
}

#[derive(Clone, Copy)]
pub(crate) struct Phy {
    mdio: Mdio,
    addr: u8,
    id: u32,
}

impl Phy {
    pub(crate) fn discover(mdio: Mdio, preferred: Option<u8>) -> Result<Self, Error> {
        if let Some(addr) = preferred {
            return Self::probe_addr(mdio, addr);
        }

        for addr in 0..32 {
            if let Ok(phy) = Self::probe_addr(mdio, addr) {
                return Ok(phy);
            }
        }
        Err(Error::PhyNotFound)
    }

    pub(crate) fn configure(self) -> Result<(), Error> {
        self.mdio.write(
            self.addr,
            MII_ADVERTISE,
            ADVERTISE_CSMA
                | ADVERTISE_10HALF
                | ADVERTISE_10FULL
                | ADVERTISE_100HALF
                | ADVERTISE_100FULL,
        )?;
        self.mdio.write(
            self.addr,
            MII_BMCR,
            BMCR_ANENABLE | BMCR_ANRESTART | BMCR_SPEED100 | BMCR_FULLDPLX,
        )
    }

    pub(crate) fn status(self) -> Result<PhyStatus, Error> {
        let first = self.mdio.read(self.addr, MII_BMSR)?;
        let second = self.mdio.read(self.addr, MII_BMSR)?;
        let bmsr = first | second;
        Ok(PhyStatus {
            addr: self.addr,
            id: self.id,
            link_up: bmsr & BMSR_LSTATUS != 0,
            autoneg_complete: bmsr & BMSR_ANEGCOMPLETE != 0,
        })
    }

    fn probe_addr(mdio: Mdio, addr: u8) -> Result<Self, Error> {
        let id1 = mdio.read(addr, MII_PHYSID1)?;
        let id2 = mdio.read(addr, MII_PHYSID2)?;
        if id1 == 0 || id1 == 0xffff || id2 == 0 || id2 == 0xffff {
            return Err(Error::PhyNotFound);
        }
        Ok(Self {
            mdio,
            addr,
            id: (u32::from(id1) << 16) | u32::from(id2),
        })
    }
}

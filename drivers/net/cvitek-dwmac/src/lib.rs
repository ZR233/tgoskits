#![no_std]

extern crate alloc;

use alloc::boxed::Box;
use core::{fmt, ptr::NonNull};

use dma_api::{CoherentArray, DeviceDma, DmaOp};
use log::info;
use mmio_api::{MmioAddr, MmioRaw};
use rdif_eth::{DriverGeneric, Event, IRxQueue, ITxQueue, Interface, NetError, QueueConfig};

pub mod cvitek_ephy;
mod descriptor;
mod mdio;
mod phy;
mod queue;
mod regs;

use descriptor::DmaDesc;
use mdio::Mdio;
use phy::Phy;
pub use phy::PhyStatus;
use queue::{RX_QUEUE_ID, RxQueue, TX_QUEUE_ID, TxQueue};
use regs::{
    DMA_STATUS_FBI, DMA_STATUS_RI, DMA_STATUS_RPS, DMA_STATUS_RU, DMA_STATUS_TI, DMA_STATUS_TPS,
    DMA_STATUS_TU, Regs,
};

const DRIVER_NAME: &str = "cvitek-dwmac";
const DEFAULT_RING_SIZE: usize = 64;
const DEFAULT_BUFFER_SIZE: usize = 1536;
const DEFAULT_DMA_ALIGN: usize = 32;
const DEFAULT_DMA_MASK: u64 = (1_u64 << 40) - 1;

fn is_usable_mac(mac: [u8; 6]) -> bool {
    mac != [0; 6] && mac != [0xff; 6] && mac[0] & 0x01 == 0
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PhyMode {
    Rmii,
    Mii,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CvitekDwmacConfig {
    pub mac_address: [u8; 6],
    pub dma_mask: u64,
    pub ring_size: usize,
    pub buffer_size: usize,
    pub dma_align: usize,
    pub txpbl: u8,
    pub rxpbl: u8,
    pub phy_mode: PhyMode,
    pub phy_addr: Option<u8>,
    pub configure_phy: bool,
    pub preserve_firmware_mac: bool,
}

impl CvitekDwmacConfig {
    pub const fn new(mac_address: [u8; 6]) -> Self {
        Self {
            mac_address,
            dma_mask: DEFAULT_DMA_MASK,
            ring_size: DEFAULT_RING_SIZE,
            buffer_size: DEFAULT_BUFFER_SIZE,
            dma_align: DEFAULT_DMA_ALIGN,
            txpbl: 8,
            rxpbl: 8,
            phy_mode: PhyMode::Rmii,
            phy_addr: None,
            configure_phy: true,
            preserve_firmware_mac: false,
        }
    }

    pub const fn queue_config(self) -> QueueConfig {
        QueueConfig {
            dma_mask: self.dma_mask,
            align: self.dma_align,
            buf_size: self.buffer_size,
            ring_size: self.ring_size,
        }
    }

    fn validate(self) -> Result<(), Error> {
        if self.ring_size < 4
            || self.buffer_size < 1536
            || self.dma_align == 0
            || !is_usable_mac(self.mac_address)
        {
            return Err(Error::InvalidConfig);
        }
        if !matches!(self.phy_mode, PhyMode::Rmii | PhyMode::Mii) {
            return Err(Error::UnsupportedPhyMode);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    InvalidConfig,
    UnsupportedPhyMode,
    Dma,
    DmaAddressTooWide,
    ResetTimeout,
    MdioTimeout,
    PhyNotFound,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig => f.write_str("invalid CVitek DWMAC configuration"),
            Self::UnsupportedPhyMode => f.write_str("unsupported CVitek DWMAC PHY mode"),
            Self::Dma => f.write_str("CVitek DWMAC DMA allocation failed"),
            Self::DmaAddressTooWide => {
                f.write_str("CVitek DWMAC DMA address exceeds descriptor width")
            }
            Self::ResetTimeout => f.write_str("CVitek DWMAC DMA reset timed out"),
            Self::MdioTimeout => f.write_str("CVitek DWMAC MDIO transaction timed out"),
            Self::PhyNotFound => f.write_str("CVitek DWMAC PHY was not found"),
        }
    }
}

impl core::error::Error for Error {}

impl From<dma_api::DmaError> for Error {
    fn from(_: dma_api::DmaError) -> Self {
        Self::Dma
    }
}

impl From<Error> for NetError {
    fn from(value: Error) -> Self {
        match value {
            Error::Dma => NetError::NoMemory,
            Error::PhyNotFound => NetError::LinkDown,
            err => NetError::Other(Box::new(err)),
        }
    }
}

pub struct CvitekDwmac {
    regs: Regs,
    _mmio: MmioRaw,
    dma: DeviceDma,
    config: CvitekDwmacConfig,
    phy: Option<Phy>,
    tx_created: bool,
    rx_created: bool,
}

impl CvitekDwmac {
    /// Creates a portable CVitek DWMAC core from an already mapped MMIO window.
    ///
    /// # Safety
    ///
    /// `virt` must point to a live MMIO mapping for the `phys..phys + size`
    /// range, and that mapping must outlive the returned driver and all queues
    /// created from it.
    pub unsafe fn new(
        phys: usize,
        virt: NonNull<u8>,
        size: usize,
        dma_op: &'static dyn DmaOp,
        mut config: CvitekDwmacConfig,
    ) -> Result<Self, Error> {
        config.validate()?;
        let mmio = unsafe { MmioRaw::new(MmioAddr::from(phys), virt, size) };
        let regs = Regs::new(virt);
        let dma = DeviceDma::new_legacy(config.dma_mask, dma_op);

        let firmware_mac = regs.read_mac_address();
        if config.preserve_firmware_mac && is_usable_mac(firmware_mac) {
            info!(
                "cvitek-dwmac using firmware MAC {:02x?} instead of fallback {:02x?}",
                firmware_mac, config.mac_address
            );
            config.mac_address = firmware_mac;
        }

        regs.stop_tx_rx();
        regs.disable_irq();
        if !regs.reset_dma() {
            return Err(Error::ResetTimeout);
        }
        regs.init_dma_bus(config.txpbl, config.rxpbl);
        regs.init_axi_bus();
        regs.init_mac(config.mac_address);
        regs.configure_store_forward();
        info!(
            "cvitek-dwmac hw_feature={:#010x} axi_bus={:#010x}",
            regs.hw_feature(),
            regs.axi_bus_mode()
        );

        let mdio = Mdio::new(regs);
        let phy = if config.configure_phy {
            let phy = Phy::discover(mdio, config.phy_addr)?;
            phy.configure()?;
            Some(phy)
        } else {
            None
        };

        Ok(Self {
            regs,
            _mmio: mmio,
            dma,
            config,
            phy,
            tx_created: false,
            rx_created: false,
        })
    }

    pub fn phy_status(&self) -> Result<Option<PhyStatus>, Error> {
        self.phy.map(Phy::status).transpose()
    }

    pub fn hw_feature(&self) -> u32 {
        self.regs.hw_feature()
    }

    pub fn missed_frame_counter(&self) -> u32 {
        self.regs.missed_frame_counter()
    }

    fn alloc_desc_ring(&self) -> Result<CoherentArray<DmaDesc>, Error> {
        Ok(self.dma.coherent_array_zero_with_align::<DmaDesc>(
            self.config.ring_size,
            DmaDesc::ALIGN.max(self.config.dma_align),
        )?)
    }
}

impl DriverGeneric for CvitekDwmac {
    fn name(&self) -> &str {
        DRIVER_NAME
    }
}

impl Interface for CvitekDwmac {
    fn mac_address(&self) -> [u8; 6] {
        self.config.mac_address
    }

    fn create_tx_queue(&mut self) -> Option<Box<dyn ITxQueue>> {
        if self.tx_created {
            return None;
        }
        let desc = self.alloc_desc_ring().ok()?;
        let queue = TxQueue::new(self.regs, desc, self.config.queue_config()).ok()?;
        self.tx_created = true;
        Some(Box::new(queue))
    }

    fn create_rx_queue(&mut self) -> Option<Box<dyn IRxQueue>> {
        if self.rx_created {
            return None;
        }
        let desc = self.alloc_desc_ring().ok()?;
        let queue = RxQueue::new(self.regs, desc, self.config.queue_config()).ok()?;
        self.rx_created = true;
        Some(Box::new(queue))
    }

    fn enable_irq(&mut self) {
        self.regs.enable_irq();
    }

    fn disable_irq(&mut self) {
        self.regs.disable_irq();
    }

    fn is_irq_enabled(&self) -> bool {
        self.regs.irq_enabled()
    }

    fn handle_irq(&mut self) -> Event {
        irq_event(self.regs.take_dma_status())
    }

    fn take_irq_handler(&mut self) -> Option<rdif_eth::BIrqHandler> {
        Some(Box::new(DwmacIrqHandler { regs: self.regs }))
    }
}

struct DwmacIrqHandler {
    regs: Regs,
}

impl rdif_eth::IrqHandler for DwmacIrqHandler {
    fn handle_irq(&mut self) -> Event {
        irq_event(self.regs.take_dma_status())
    }
}

fn irq_event(status: u32) -> Event {
    let mut event = Event::none();
    if status & (DMA_STATUS_TI | DMA_STATUS_TPS | DMA_STATUS_TU | DMA_STATUS_FBI) != 0 {
        event.tx_queue.insert(TX_QUEUE_ID);
    }
    if status & (DMA_STATUS_RI | DMA_STATUS_RU | DMA_STATUS_RPS | DMA_STATUS_FBI) != 0 {
        event.rx_queue.insert(RX_QUEUE_ID);
    }
    event
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_defaults_match_sg2002_constraints() {
        let cfg = CvitekDwmacConfig::new([2, 0, 0, 0x20, 0x02, 0]);
        assert_eq!(cfg.dma_mask, (1_u64 << 40) - 1);
        assert_eq!(cfg.phy_mode, PhyMode::Rmii);
        assert!(!cfg.preserve_firmware_mac);
        assert!(cfg.validate().is_ok());
    }

    #[test]
    fn mac_validation_rejects_empty_broadcast_and_multicast() {
        assert!(!is_usable_mac([0; 6]));
        assert!(!is_usable_mac([0xff; 6]));
        assert!(!is_usable_mac([0x01, 0, 0, 0, 0, 0]));
        assert!(is_usable_mac([0x96, 0xce, 0xb6, 0xce, 0xe1, 0x20]));
    }

    #[test]
    fn irq_status_fans_out_to_queue_events() {
        let ev = irq_event(DMA_STATUS_TI | DMA_STATUS_RI);
        assert!(ev.tx_queue.contains(TX_QUEUE_ID));
        assert!(ev.rx_queue.contains(RX_QUEUE_ID));
    }
}

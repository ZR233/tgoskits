use core::ptr::NonNull;

pub(crate) const GMAC_CONTROL: usize = 0x0000;
const GMAC_FRAME_FILTER: usize = 0x0004;
const GMAC_MII_ADDR: usize = 0x0010;
const GMAC_MII_DATA: usize = 0x0014;
const GMAC_FLOW_CTRL: usize = 0x0018;
const GMAC_DEBUG: usize = 0x0024;
const GMAC_INT_MASK: usize = 0x003c;
const GMAC_ADDR0_HIGH: usize = 0x0040;
const GMAC_ADDR0_LOW: usize = 0x0044;

const DMA_BUS_MODE: usize = 0x1000;
const DMA_TX_POLL_DEMAND: usize = 0x1004;
const DMA_RX_POLL_DEMAND: usize = 0x1008;
const DMA_RX_BASE_ADDR: usize = 0x100c;
const DMA_TX_BASE_ADDR: usize = 0x1010;
const DMA_STATUS: usize = 0x1014;
const DMA_CONTROL: usize = 0x1018;
const DMA_INTR_ENA: usize = 0x101c;
const DMA_MISSED_FRAME_CTR: usize = 0x1020;
const DMA_AXI_BUS_MODE: usize = 0x1028;
const DMA_CUR_RX_BUF_ADDR: usize = 0x1054;
const DMA_HW_FEATURE: usize = 0x1058;

const DMA_BUS_MODE_SFT_RESET: u32 = 1;
const DMA_BUS_MODE_PBL_SHIFT: u32 = 8;
const DMA_BUS_MODE_RPBL_SHIFT: u32 = 17;
const DMA_BUS_MODE_USP: u32 = 1 << 23;
const DMA_BUS_MODE_AAL: u32 = 1 << 25;

const DMA_AXI_WR_OSR_LMT_MASK: u32 = 0xf << 20;
const DMA_AXI_WR_OSR_LMT_SHIFT: u32 = 20;
const DMA_AXI_RD_OSR_LMT_MASK: u32 = 0xf << 16;
const DMA_AXI_RD_OSR_LMT_SHIFT: u32 = 16;
const DMA_AXI_BURST_LEN_MASK: u32 = 0x0000_00fe;
const DMA_AXI_BLEN16: u32 = 1 << 3;
const DMA_AXI_BLEN8: u32 = 1 << 2;
const DMA_AXI_BLEN4: u32 = 1 << 1;

const DMA_CONTROL_SR: u32 = 1 << 1;
const DMA_CONTROL_ST: u32 = 1 << 13;
const DMA_CONTROL_OSF: u32 = 1 << 2;
const DMA_CONTROL_TSF: u32 = 1 << 21;
const DMA_CONTROL_RSF: u32 = 1 << 25;

pub(crate) const DMA_STATUS_TI: u32 = 1 << 0;
pub(crate) const DMA_STATUS_TPS: u32 = 1 << 1;
pub(crate) const DMA_STATUS_TU: u32 = 1 << 2;
pub(crate) const DMA_STATUS_RI: u32 = 1 << 6;
pub(crate) const DMA_STATUS_RU: u32 = 1 << 7;
pub(crate) const DMA_STATUS_RPS: u32 = 1 << 8;
pub(crate) const DMA_STATUS_FBI: u32 = 1 << 13;
pub(crate) const DMA_STATUS_NIS: u32 = 1 << 16;
pub(crate) const DMA_STATUS_AIS: u32 = 1 << 15;
pub(crate) const DMA_STATUS_ACK_MASK: u32 = DMA_STATUS_TI
    | DMA_STATUS_TPS
    | DMA_STATUS_TU
    | DMA_STATUS_RI
    | DMA_STATUS_RU
    | DMA_STATUS_RPS
    | DMA_STATUS_FBI
    | DMA_STATUS_NIS
    | DMA_STATUS_AIS;

const DMA_INTR_ENA_NIE: u32 = 1 << 16;
const DMA_INTR_ENA_AIE: u32 = 1 << 15;
const DMA_INTR_ENA_FBE: u32 = 1 << 13;
const DMA_INTR_ENA_RIE: u32 = 1 << 6;
const DMA_INTR_ENA_TIE: u32 = 1 << 0;
const DMA_INTR_DEFAULT_MASK: u32 =
    DMA_INTR_ENA_NIE | DMA_INTR_ENA_AIE | DMA_INTR_ENA_FBE | DMA_INTR_ENA_RIE | DMA_INTR_ENA_TIE;

const GMAC_CONTROL_JD: u32 = 1 << 22;
const GMAC_CONTROL_BE: u32 = 1 << 21;
const GMAC_CONTROL_DCRS: u32 = 1 << 16;
const GMAC_CONTROL_PS: u32 = 1 << 15;
const GMAC_CONTROL_FES: u32 = 1 << 14;
const GMAC_CONTROL_DM: u32 = 1 << 11;
const GMAC_CONTROL_IPC: u32 = 1 << 10;
const GMAC_CONTROL_ACS: u32 = 1 << 7;
const GMAC_CONTROL_TE: u32 = 1 << 3;
const GMAC_CONTROL_RE: u32 = 1 << 2;

const GMAC_FRAME_FILTER_HPF: u32 = 1 << 10;

const GMAC_INT_DEFAULT_MASK: u32 = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 9);
const GMAC_ADDR_HIGH_AE: u32 = 1 << 31;

#[derive(Clone, Copy)]
pub(crate) struct Regs {
    base: NonNull<u8>,
}

unsafe impl Send for Regs {}
unsafe impl Sync for Regs {}

impl Regs {
    pub(crate) const fn new(base: NonNull<u8>) -> Self {
        Self { base }
    }

    #[inline]
    pub(crate) fn read(self, offset: usize) -> u32 {
        unsafe { self.base.as_ptr().add(offset).cast::<u32>().read_volatile() }
    }

    #[inline]
    pub(crate) fn write(self, offset: usize, value: u32) {
        unsafe {
            self.base
                .as_ptr()
                .add(offset)
                .cast::<u32>()
                .write_volatile(value)
        }
    }

    pub(crate) fn reset_dma(self) -> bool {
        self.write(
            DMA_BUS_MODE,
            self.read(DMA_BUS_MODE) | DMA_BUS_MODE_SFT_RESET,
        );
        for _ in 0..200_000 {
            if self.read(DMA_BUS_MODE) & DMA_BUS_MODE_SFT_RESET == 0 {
                return true;
            }
            core::hint::spin_loop();
        }
        false
    }

    pub(crate) fn init_dma_bus(self, txpbl: u8, rxpbl: u8) {
        let mut value = self.read(DMA_BUS_MODE);
        value |= DMA_BUS_MODE_USP | DMA_BUS_MODE_AAL;
        value &= !((0x3f << DMA_BUS_MODE_PBL_SHIFT) | (0x3f << DMA_BUS_MODE_RPBL_SHIFT));
        value |= (u32::from(txpbl.min(32)) << DMA_BUS_MODE_PBL_SHIFT)
            | (u32::from(rxpbl.min(32)) << DMA_BUS_MODE_RPBL_SHIFT);
        self.write(DMA_BUS_MODE, value);
    }

    pub(crate) fn init_axi_bus(self) {
        let mut value = self.read(DMA_AXI_BUS_MODE);
        value &= !(DMA_AXI_WR_OSR_LMT_MASK | DMA_AXI_RD_OSR_LMT_MASK | DMA_AXI_BURST_LEN_MASK);
        value |= (1 << DMA_AXI_WR_OSR_LMT_SHIFT)
            | (2 << DMA_AXI_RD_OSR_LMT_SHIFT)
            | DMA_AXI_BLEN16
            | DMA_AXI_BLEN8
            | DMA_AXI_BLEN4;
        self.write(DMA_AXI_BUS_MODE, value);
    }

    pub(crate) fn init_mac(self, mac: [u8; 6]) {
        self.write(DMA_INTR_ENA, 0);
        self.write(GMAC_INT_MASK, GMAC_INT_DEFAULT_MASK);
        self.write(GMAC_FLOW_CTRL, 0);
        self.write(GMAC_FRAME_FILTER, GMAC_FRAME_FILTER_HPF);
        self.write_mac_address(mac);
        self.write(
            GMAC_CONTROL,
            GMAC_CONTROL_JD
                | GMAC_CONTROL_BE
                | GMAC_CONTROL_DCRS
                | GMAC_CONTROL_PS
                | GMAC_CONTROL_FES
                | GMAC_CONTROL_DM
                | GMAC_CONTROL_IPC
                | GMAC_CONTROL_ACS
                | GMAC_CONTROL_TE
                | GMAC_CONTROL_RE,
        );
    }

    pub(crate) fn read_mac_address(self) -> [u8; 6] {
        let low = self.read(GMAC_ADDR0_LOW);
        let high = self.read(GMAC_ADDR0_HIGH);
        [
            (low & 0xff) as u8,
            ((low >> 8) & 0xff) as u8,
            ((low >> 16) & 0xff) as u8,
            ((low >> 24) & 0xff) as u8,
            (high & 0xff) as u8,
            ((high >> 8) & 0xff) as u8,
        ]
    }

    pub(crate) fn configure_store_forward(self) {
        self.write(
            DMA_CONTROL,
            self.read(DMA_CONTROL) | DMA_CONTROL_TSF | DMA_CONTROL_RSF | DMA_CONTROL_OSF,
        );
    }

    pub(crate) fn write_rx_desc_base(self, addr: u64) {
        self.write(DMA_RX_BASE_ADDR, addr as u32);
    }

    pub(crate) fn write_tx_desc_base(self, addr: u64) {
        self.write(DMA_TX_BASE_ADDR, addr as u32);
    }

    pub(crate) fn start_tx(self) {
        self.write(DMA_CONTROL, self.read(DMA_CONTROL) | DMA_CONTROL_ST);
        self.write(GMAC_CONTROL, self.read(GMAC_CONTROL) | GMAC_CONTROL_TE);
    }

    pub(crate) fn start_rx(self) {
        self.write(DMA_CONTROL, self.read(DMA_CONTROL) | DMA_CONTROL_SR);
        self.write(GMAC_CONTROL, self.read(GMAC_CONTROL) | GMAC_CONTROL_RE);
    }

    pub(crate) fn stop_tx_rx(self) {
        self.write(
            DMA_CONTROL,
            self.read(DMA_CONTROL) & !(DMA_CONTROL_ST | DMA_CONTROL_SR),
        );
        self.write(
            GMAC_CONTROL,
            self.read(GMAC_CONTROL) & !(GMAC_CONTROL_TE | GMAC_CONTROL_RE),
        );
    }

    pub(crate) fn enable_irq(self) {
        self.write(DMA_STATUS, DMA_STATUS_ACK_MASK);
        self.write(DMA_INTR_ENA, DMA_INTR_DEFAULT_MASK);
    }

    pub(crate) fn disable_irq(self) {
        self.write(DMA_INTR_ENA, 0);
    }

    pub(crate) fn irq_enabled(self) -> bool {
        self.read(DMA_INTR_ENA) != 0
    }

    pub(crate) fn take_dma_status(self) -> u32 {
        let status = self.read(DMA_STATUS);
        let ack = status & DMA_STATUS_ACK_MASK;
        if ack != 0 {
            self.write(DMA_STATUS, ack);
        }
        status
    }

    pub(crate) fn dma_status(self) -> u32 {
        self.read(DMA_STATUS)
    }

    pub(crate) fn poll_tx(self) {
        self.write(DMA_TX_POLL_DEMAND, 0);
    }

    pub(crate) fn poll_rx(self) {
        self.write(DMA_RX_POLL_DEMAND, 0);
    }

    pub(crate) fn hw_feature(self) -> u32 {
        self.read(DMA_HW_FEATURE)
    }

    pub(crate) fn axi_bus_mode(self) -> u32 {
        self.read(DMA_AXI_BUS_MODE)
    }

    pub(crate) fn current_rx_buffer(self) -> u32 {
        self.read(DMA_CUR_RX_BUF_ADDR)
    }

    pub(crate) fn gmac_debug(self) -> u32 {
        self.read(GMAC_DEBUG)
    }

    pub(crate) fn missed_frame_counter(self) -> u32 {
        self.read(DMA_MISSED_FRAME_CTR)
    }

    pub(crate) fn mii_addr(self) -> u32 {
        self.read(GMAC_MII_ADDR)
    }

    pub(crate) fn write_mii_addr(self, value: u32) {
        self.write(GMAC_MII_ADDR, value);
    }

    pub(crate) fn mii_data(self) -> u32 {
        self.read(GMAC_MII_DATA)
    }

    pub(crate) fn write_mii_data(self, value: u32) {
        self.write(GMAC_MII_DATA, value);
    }

    fn write_mac_address(self, mac: [u8; 6]) {
        let low = u32::from(mac[0])
            | (u32::from(mac[1]) << 8)
            | (u32::from(mac[2]) << 16)
            | (u32::from(mac[3]) << 24);
        let high = u32::from(mac[4]) | (u32::from(mac[5]) << 8) | GMAC_ADDR_HIGH_AE;
        self.write(GMAC_ADDR0_LOW, low);
        self.write(GMAC_ADDR0_HIGH, high);
    }
}

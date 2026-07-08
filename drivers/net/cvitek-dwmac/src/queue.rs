use alloc::vec::Vec;
use core::sync::atomic::{Ordering, fence};

use dma_api::CoherentArray;
use log::{info, warn};
use rdif_eth::{DmaBuffer, IRxQueue, ITxQueue, NetError, QueueConfig};

use crate::{
    Error,
    descriptor::{DmaDesc, desc_ring_bytes},
    regs::Regs,
};

pub(crate) const TX_QUEUE_ID: usize = 0;
pub(crate) const RX_QUEUE_ID: usize = 0;
const TX_LOG_BUDGET: u8 = 8;
const RX_LOG_BUDGET: u8 = 8;
const RX_IDLE_LOG_BUDGET: u8 = 12;

pub(crate) struct TxQueue {
    regs: Regs,
    desc: CoherentArray<DmaDesc>,
    bus_addrs: Vec<Option<u64>>,
    next_submit: usize,
    next_reclaim: usize,
    config: QueueConfig,
    submit_log_budget: u8,
    reclaim_log_budget: u8,
}

impl TxQueue {
    pub(crate) fn new(
        regs: Regs,
        mut desc: CoherentArray<DmaDesc>,
        config: QueueConfig,
    ) -> Result<Self, Error> {
        for idx in 0..desc.len() {
            desc.set_cpu(idx, DmaDesc::empty_tx(idx == desc.len() - 1));
        }
        let base = desc.dma_addr().as_u64();
        if base > u32::MAX as u64 || base + desc_ring_bytes(desc.len()) as u64 > u32::MAX as u64 {
            return Err(Error::DmaAddressTooWide);
        }
        regs.write_tx_desc_base(base);
        regs.start_tx();
        info!(
            "cvitek-dwmac tx ring base={:#x} entries={} buf_size={}",
            base,
            desc.len(),
            config.buf_size
        );
        Ok(Self {
            regs,
            bus_addrs: alloc::vec![None; desc.len()],
            desc,
            next_submit: 0,
            next_reclaim: 0,
            config,
            submit_log_budget: TX_LOG_BUDGET,
            reclaim_log_budget: TX_LOG_BUDGET,
        })
    }
}

impl ITxQueue for TxQueue {
    fn id(&self) -> usize {
        TX_QUEUE_ID
    }

    fn config(&self) -> QueueConfig {
        self.config
    }

    fn submit(&mut self, buffer: DmaBuffer) -> Result<(), NetError> {
        if buffer.len > self.config.buf_size {
            return Err(NetError::NotSupported);
        }

        let idx = self.next_submit;
        if self.bus_addrs[idx].is_some() {
            return Err(NetError::Retry);
        }

        let desc = DmaDesc::tx(buffer.bus_addr, buffer.len, idx == self.desc.len() - 1)
            .ok_or(NetError::NotSupported)?;
        self.desc.set_cpu(idx, desc);
        release_to_device();
        let hw_desc = desc.release_tx_to_hw();
        self.desc.set_cpu(idx, hw_desc);
        if self.submit_log_budget > 0 {
            info!(
                "cvitek-dwmac tx submit idx={} len={} bus={:#x} des0={:#010x} des1={:#010x} \
                 dma={:#010x}",
                idx,
                buffer.len,
                buffer.bus_addr,
                hw_desc.des0,
                hw_desc.des1,
                self.regs.dma_status()
            );
            self.submit_log_budget -= 1;
        }
        self.bus_addrs[idx] = Some(buffer.bus_addr);
        self.next_submit = (idx + 1) % self.desc.len();
        self.regs.poll_tx();
        Ok(())
    }

    fn reclaim(&mut self) -> Option<u64> {
        let idx = self.next_reclaim;
        self.bus_addrs[idx]?;
        let desc = self.desc.read_cpu(idx)?;
        if desc.tx_owned_by_hw() {
            return None;
        }
        if self.reclaim_log_budget > 0 {
            if desc.tx_has_error() {
                warn!(
                    "cvitek-dwmac tx reclaim idx={} bus={:#x} des0={:#010x} des1={:#010x} \
                     error={} dma={:#010x}",
                    idx,
                    self.bus_addrs[idx]?,
                    desc.des0,
                    desc.des1,
                    true,
                    self.regs.dma_status()
                );
            } else {
                info!(
                    "cvitek-dwmac tx reclaim idx={} bus={:#x} des0={:#010x} des1={:#010x} \
                     error={} dma={:#010x}",
                    idx,
                    self.bus_addrs[idx]?,
                    desc.des0,
                    desc.des1,
                    false,
                    self.regs.dma_status()
                );
            }
            self.reclaim_log_budget -= 1;
        }
        if desc.tx_has_error() {
            self.desc
                .set_cpu(idx, DmaDesc::empty_tx(idx == self.desc.len() - 1));
        }
        self.next_reclaim = (idx + 1) % self.desc.len();
        self.bus_addrs[idx].take()
    }
}

pub(crate) struct RxQueue {
    regs: Regs,
    desc: CoherentArray<DmaDesc>,
    bus_addrs: Vec<Option<u64>>,
    next_submit: usize,
    next_reclaim: usize,
    config: QueueConfig,
    submit_log_budget: u8,
    idle_log_budget: u8,
    reclaim_log_budget: u8,
}

impl RxQueue {
    pub(crate) fn new(
        regs: Regs,
        desc: CoherentArray<DmaDesc>,
        config: QueueConfig,
    ) -> Result<Self, Error> {
        let base = desc.dma_addr().as_u64();
        if base > u32::MAX as u64 || base + desc_ring_bytes(desc.len()) as u64 > u32::MAX as u64 {
            return Err(Error::DmaAddressTooWide);
        }
        regs.write_rx_desc_base(base);
        let len = desc.len();
        info!(
            "cvitek-dwmac rx ring base={:#x} entries={} buf_size={}",
            base, len, config.buf_size
        );
        Ok(Self {
            regs,
            desc,
            bus_addrs: alloc::vec![None; len],
            next_submit: 0,
            next_reclaim: 0,
            config,
            submit_log_budget: RX_LOG_BUDGET,
            idle_log_budget: RX_IDLE_LOG_BUDGET,
            reclaim_log_budget: RX_LOG_BUDGET,
        })
    }
}

impl IRxQueue for RxQueue {
    fn id(&self) -> usize {
        RX_QUEUE_ID
    }

    fn config(&self) -> QueueConfig {
        self.config
    }

    fn submit(&mut self, buffer: DmaBuffer) -> Result<(), NetError> {
        if buffer.len < self.config.buf_size {
            return Err(NetError::NotSupported);
        }

        let idx = self.next_submit;
        if self.bus_addrs[idx].is_some() {
            return Err(NetError::Retry);
        }
        let desc = DmaDesc::rx(
            buffer.bus_addr,
            self.config.buf_size,
            idx == self.desc.len() - 1,
        )
        .ok_or(NetError::NotSupported)?;
        self.desc.set_cpu(idx, desc);
        release_to_device();
        self.bus_addrs[idx] = Some(buffer.bus_addr);
        self.next_submit = (idx + 1) % self.desc.len();
        self.regs.start_rx();
        self.regs.poll_rx();
        if self.submit_log_budget > 0 {
            info!(
                "cvitek-dwmac rx submit idx={} len={} bus={:#x} des0={:#010x} des1={:#010x} \
                 dma={:#010x} missed={:#010x}",
                idx,
                self.config.buf_size,
                buffer.bus_addr,
                desc.des0,
                desc.des1,
                self.regs.dma_status(),
                self.regs.missed_frame_counter()
            );
            self.submit_log_budget -= 1;
        }
        Ok(())
    }

    fn reclaim(&mut self) -> Option<(u64, usize)> {
        let idx = self.next_reclaim;
        let bus_addr = self.bus_addrs[idx]?;
        let desc = self.desc.read_cpu(idx)?;
        if desc.rx_owned_by_hw() {
            if self.idle_log_budget > 0 {
                info!(
                    "cvitek-dwmac rx idle idx={} bus={:#x} des0={:#010x} des1={:#010x} \
                     dma={:#010x} cur_rx={:#010x} mac_dbg={:#010x} missed={:#010x}",
                    idx,
                    bus_addr,
                    desc.des0,
                    desc.des1,
                    self.regs.dma_status(),
                    self.regs.current_rx_buffer(),
                    self.regs.gmac_debug(),
                    self.regs.missed_frame_counter()
                );
                self.idle_log_budget -= 1;
            }
            return None;
        }

        self.next_reclaim = (idx + 1) % self.desc.len();
        self.bus_addrs[idx] = None;
        if self.reclaim_log_budget > 0 {
            let len = desc.rx_frame_len().min(self.config.buf_size);
            if desc.rx_error() || !desc.rx_complete_single_frame() {
                warn!(
                    "cvitek-dwmac rx reclaim idx={} bus={:#x} len={} des0={:#010x} des1={:#010x} \
                     error={} single={} dma={:#010x}",
                    idx,
                    bus_addr,
                    len,
                    desc.des0,
                    desc.des1,
                    desc.rx_error(),
                    desc.rx_complete_single_frame(),
                    self.regs.dma_status()
                );
            } else {
                info!(
                    "cvitek-dwmac rx reclaim idx={} bus={:#x} len={} des0={:#010x} des1={:#010x} \
                     error={} single={} dma={:#010x}",
                    idx,
                    bus_addr,
                    len,
                    desc.des0,
                    desc.des1,
                    desc.rx_error(),
                    desc.rx_complete_single_frame(),
                    self.regs.dma_status()
                );
            }
            self.reclaim_log_budget -= 1;
        }
        if desc.rx_error() || !desc.rx_complete_single_frame() {
            return Some((bus_addr, 0));
        }
        Some((bus_addr, desc.rx_frame_len().min(self.config.buf_size)))
    }
}

fn release_to_device() {
    fence(Ordering::Release);
}

use core::mem::size_of;

const RDES0_CRC_ERROR: u32 = 1 << 1;
const RDES0_MII_ERROR: u32 = 1 << 3;
const RDES0_LAST_DESCRIPTOR: u32 = 1 << 8;
const RDES0_FIRST_DESCRIPTOR: u32 = 1 << 9;
const RDES0_OVERFLOW_ERROR: u32 = 1 << 11;
const RDES0_LENGTH_ERROR: u32 = 1 << 12;
const RDES0_DESCRIPTOR_ERROR: u32 = 1 << 14;
const RDES0_ERROR_SUMMARY: u32 = 1 << 15;
const RDES0_FRAME_LEN_MASK: u32 = 0x3fff << 16;
const RDES0_FRAME_LEN_SHIFT: u32 = 16;
const RDES0_OWN: u32 = 1 << 31;
const ETH_FCS_LEN: usize = 4;

const RDES1_BUFFER1_SIZE_MASK: u32 = 0x7ff;
const RDES1_BUFFER2_SIZE_MASK: u32 = 0x7ff << 11;
const RDES1_BUFFER2_SIZE_SHIFT: u32 = 11;
const RDES1_END_RING: u32 = 1 << 25;

const TDES0_OWN: u32 = 1 << 31;

const TDES1_BUFFER1_SIZE_MASK: u32 = 0x7ff;
const TDES1_BUFFER2_SIZE_MASK: u32 = 0x7ff << 11;
const TDES1_BUFFER2_SIZE_SHIFT: u32 = 11;
const TDES1_END_RING: u32 = 1 << 25;
const TDES1_FIRST_SEGMENT: u32 = 1 << 29;
const TDES1_LAST_SEGMENT: u32 = 1 << 30;
const TDES1_INTERRUPT: u32 = 1 << 31;

const BUF_SIZE_2K: usize = 2048;

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub(crate) struct DmaDesc {
    pub des0: u32,
    pub des1: u32,
    pub des2: u32,
    pub des3: u32,
}

impl DmaDesc {
    pub(crate) const ALIGN: usize = 16;

    pub(crate) fn empty_tx(end_ring: bool) -> Self {
        Self {
            des0: 0,
            des1: end_bit(end_ring, TDES1_END_RING),
            des2: 0,
            des3: 0,
        }
    }

    pub(crate) fn tx(buffer_addr: u64, len: usize, end_ring: bool) -> Option<Self> {
        let addr = u32::try_from(buffer_addr).ok()?;
        let len_bits = tx_len_bits(len)?;
        Some(Self {
            des0: 0,
            des1: len_bits
                | end_bit(end_ring, TDES1_END_RING)
                | TDES1_FIRST_SEGMENT
                | TDES1_LAST_SEGMENT
                | TDES1_INTERRUPT,
            des2: addr,
            des3: 0,
        })
    }

    pub(crate) const fn release_tx_to_hw(mut self) -> Self {
        self.des0 |= TDES0_OWN;
        self
    }

    pub(crate) const fn tx_owned_by_hw(self) -> bool {
        self.des0 & TDES0_OWN != 0
    }

    pub(crate) const fn tx_has_error(self) -> bool {
        self.des0 & RDES0_ERROR_SUMMARY != 0
    }

    pub(crate) fn rx(buffer_addr: u64, len: usize, end_ring: bool) -> Option<Self> {
        let addr = u32::try_from(buffer_addr).ok()?;
        let len_bits = rx_len_bits(len)?;
        Some(Self {
            des0: RDES0_OWN,
            des1: len_bits | end_bit(end_ring, RDES1_END_RING),
            des2: addr,
            des3: 0,
        })
    }

    pub(crate) const fn rx_owned_by_hw(self) -> bool {
        self.des0 & RDES0_OWN != 0
    }

    pub(crate) const fn rx_error(self) -> bool {
        self.des0
            & (RDES0_ERROR_SUMMARY
                | RDES0_DESCRIPTOR_ERROR
                | RDES0_OVERFLOW_ERROR
                | RDES0_CRC_ERROR
                | RDES0_LENGTH_ERROR
                | RDES0_MII_ERROR)
            != 0
    }

    pub(crate) const fn rx_complete_single_frame(self) -> bool {
        self.des0 & (RDES0_FIRST_DESCRIPTOR | RDES0_LAST_DESCRIPTOR)
            == (RDES0_FIRST_DESCRIPTOR | RDES0_LAST_DESCRIPTOR)
    }

    pub(crate) const fn rx_frame_len(self) -> usize {
        let wire_len = ((self.des0 & RDES0_FRAME_LEN_MASK) >> RDES0_FRAME_LEN_SHIFT) as usize;
        wire_len.saturating_sub(ETH_FCS_LEN)
    }
}

pub(crate) const fn desc_ring_bytes(count: usize) -> usize {
    count * size_of::<DmaDesc>()
}

fn end_bit(end_ring: bool, bit: u32) -> u32 {
    if end_ring { bit } else { 0 }
}

fn tx_len_bits(len: usize) -> Option<u32> {
    if len == 0 {
        return Some(0);
    }
    if len <= TDES1_BUFFER1_SIZE_MASK as usize {
        return Some(len as u32);
    }
    let first = BUF_SIZE_2K - 1;
    let second = len.checked_sub(first)?;
    if second > (TDES1_BUFFER2_SIZE_MASK >> TDES1_BUFFER2_SIZE_SHIFT) as usize {
        return None;
    }
    Some(
        (first as u32 & TDES1_BUFFER1_SIZE_MASK)
            | (((second as u32) << TDES1_BUFFER2_SIZE_SHIFT) & TDES1_BUFFER2_SIZE_MASK),
    )
}

fn rx_len_bits(len: usize) -> Option<u32> {
    if len == 0 {
        return None;
    }
    let first = len.min(BUF_SIZE_2K - 1) as u32;
    let mut bits = first & RDES1_BUFFER1_SIZE_MASK;
    if len >= BUF_SIZE_2K {
        let second = (len - BUF_SIZE_2K + 1).min(BUF_SIZE_2K - 1) as u32;
        bits |= (second << RDES1_BUFFER2_SIZE_SHIFT) & RDES1_BUFFER2_SIZE_MASK;
    }
    Some(bits)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tx_descriptor_ownership_and_length_bits() {
        let desc = DmaDesc::tx(0x8000_1000, 1500, true).unwrap();
        assert!(!desc.tx_owned_by_hw());
        assert_eq!(desc.des1 & TDES1_BUFFER1_SIZE_MASK, 1500);
        assert_ne!(desc.des1 & TDES1_END_RING, 0);

        let hw = desc.release_tx_to_hw();
        assert!(hw.tx_owned_by_hw());
    }

    #[test]
    fn tx_descriptor_rejects_unaddressable_buffer() {
        assert!(DmaDesc::tx(0x1_0000_0000, 64, false).is_none());
    }

    #[test]
    fn rx_descriptor_ownership_and_frame_len() {
        let desc = DmaDesc::rx(0x8000_2000, 2048, true).unwrap();
        assert!(desc.rx_owned_by_hw());
        assert_ne!(desc.des1 & RDES1_END_RING, 0);

        let done = DmaDesc {
            des0: RDES0_FIRST_DESCRIPTOR
                | RDES0_LAST_DESCRIPTOR
                | ((96 + ETH_FCS_LEN as u32) << RDES0_FRAME_LEN_SHIFT),
            ..desc
        };
        assert!(!done.rx_owned_by_hw());
        assert!(done.rx_complete_single_frame());
        assert_eq!(done.rx_frame_len(), 96);
    }

    #[test]
    fn rx_frame_len_saturates_when_hardware_reports_short_frame() {
        let done = DmaDesc {
            des0: RDES0_FIRST_DESCRIPTOR | RDES0_LAST_DESCRIPTOR | (2 << RDES0_FRAME_LEN_SHIFT),
            ..DmaDesc::default()
        };
        assert_eq!(done.rx_frame_len(), 0);
    }
}

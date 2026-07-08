use alloc::{format, string::ToString};

use cvitek_dwmac::{
    CvitekDwmac, CvitekDwmacConfig, PhyMode,
    cvitek_ephy::{self, EphyMmio, EphyTuning},
};
use log::{info, warn};
use rdrive::{
    probe::{OnProbeError, fdt::ResourcePrepareConfig},
    register::ProbeFdt,
};

use crate::{binding_info_from_fdt, mmio::iomap, net::PlatformDeviceNet};

const DRIVER_NAME: &str = "cvitek-dwmac";
const COMPATIBLE: &str = "cvitek,ethernet";
const DEFAULT_MMIO_SIZE: u64 = 0x10000;

crate::model_register!(
    name: "CVitek DWMAC Ethernet",
    level: ProbeLevel::PostKernel,
    priority: ProbePriority::DEFAULT,
    probe_kinds: &[ProbeKind::Fdt {
        compatibles: &[COMPATIBLE],
        on_probe: probe_fdt,
    }],
);

fn probe_fdt(probe: ProbeFdt<'_>) -> Result<(), OnProbeError> {
    let info = probe.info();
    let node = info.node.as_node();
    let base_reg = info
        .node
        .regs()
        .into_iter()
        .next()
        .ok_or_else(|| OnProbeError::other(format!("[{}] has no reg", info.node.name())))?;
    let node_name = info.node.name().to_string();
    let mmio_address = base_reg.address;
    let size = base_reg.size.unwrap_or(DEFAULT_MMIO_SIZE) as usize;

    let resources = info.prepare_resources(
        ResourcePrepareConfig::default()
            .with_assigned_clocks()
            .with_named_clock_rate("stmmaceth")
            .with_named_clock_rate("ptp_ref")
            .with_named_clock_rate("clk_500m_eth")
            .with_named_clock_rate("clk_axi4_eth"),
    )?;
    for name in ["stmmaceth", "ptp_ref", "clk_500m_eth", "clk_axi4_eth"] {
        if let Some(rate) = resources.clock_rate(name) {
            info!("cvitek-dwmac clock {name} rate {rate} Hz");
        }
    }

    if node.get_property("phy-reset-gpios").is_some() {
        warn!("cvitek-dwmac: phy-reset-gpios is present, GPIO reset glue is not implemented yet");
    }
    if node.get_property("phy-handle").is_some() {
        warn!(
            "cvitek-dwmac: phy-handle is present; this SG2002 path scans the MDIO bus and does \
             not consume a separate PHY node yet"
        );
    }

    let fdt_mac_address = mac_address_from_fdt(node);
    let mac_address = fdt_mac_address.unwrap_or_else(default_mac_address);
    let config = config_from_fdt(node, mac_address, fdt_mac_address.is_none())?;
    let mmio = iomap(mmio_address as usize, size)?;
    init_cvitek_ephy()?;
    let dev =
        unsafe { CvitekDwmac::new(mmio_address as usize, mmio, size, axklib::dma::op(), config) }
            .map_err(|err| {
            OnProbeError::other(format!("failed to initialize cvitek-dwmac: {err:?}"))
        })?;
    let phy_status = dev.phy_status();

    let binding = binding_info_from_fdt(info)?;
    let irq = probe
        .into_platform_device()
        .register_net_with_info(DRIVER_NAME, dev, binding);
    info!(
        "registered CVitek DWMAC ethernet node={} addr={:#x} size={:#x} irq={irq:?} link={:?}",
        node_name, mmio_address, size, phy_status
    );
    Ok(())
}

fn mac_address_from_fdt(node: &fdt_edit::Node) -> Option<[u8; 6]> {
    ["local-mac-address", "mac-address"]
        .into_iter()
        .find_map(|name| {
            let prop = node.get_property(name)?;
            (prop.data.len() == 6).then(|| {
                let mut mac = [0_u8; 6];
                mac.copy_from_slice(&prop.data[..6]);
                mac
            })
        })
}

fn default_mac_address() -> [u8; 6] {
    [0x02, 0x00, 0x00, 0x20, 0x02, 0x00]
}

fn config_from_fdt(
    node: &fdt_edit::Node,
    mac_address: [u8; 6],
    preserve_firmware_mac: bool,
) -> Result<CvitekDwmacConfig, OnProbeError> {
    let mut config = CvitekDwmacConfig::new(mac_address);
    config.preserve_firmware_mac = preserve_firmware_mac;
    config.phy_mode = match prop_str(node, "phy-mode").unwrap_or("rmii") {
        "rmii" => PhyMode::Rmii,
        "mii" => PhyMode::Mii,
        other => {
            return Err(OnProbeError::other(format!(
                "cvitek-dwmac unsupported phy-mode {other}"
            )));
        }
    };
    if let Some(txpbl) = prop_u32(node, "snps,txpbl") {
        config.txpbl = pbl_u8("snps,txpbl", txpbl)?;
    }
    if let Some(rxpbl) = prop_u32(node, "snps,rxpbl") {
        config.rxpbl = pbl_u8("snps,rxpbl", rxpbl)?;
    }
    if let Some(phy_addr) = prop_u32(node, "phy-address").or_else(|| prop_u32(node, "phy-addr")) {
        config.phy_addr = Some(phy_addr as u8);
    }
    Ok(config)
}

fn init_cvitek_ephy() -> Result<(), OnProbeError> {
    let top_wrap = iomap(
        cvitek_ephy::EPHY_TOP_WRAP_BASE,
        cvitek_ephy::EPHY_TOP_WRAP_SIZE,
    )?;
    let analog = iomap(cvitek_ephy::EPHY_BASE, cvitek_ephy::EPHY_ANALOG_SIZE)?;
    let mmio = EphyMmio { top_wrap, analog };
    cvitek_ephy::init(mmio, EphyTuning::default())
        .map_err(|err| OnProbeError::other(format!("failed to initialize CVitek EPHY: {err:?}")))?;
    info!("cvitek-dwmac applied CVitek EPHY fallback init sequence from Linux semantic reference");
    Ok(())
}

fn prop_u32(node: &fdt_edit::Node, name: &str) -> Option<u32> {
    node.get_property(name).and_then(|prop| prop.get_u32())
}

fn prop_str<'a>(node: &'a fdt_edit::Node, name: &str) -> Option<&'a str> {
    node.get_property(name).and_then(|prop| prop.as_str())
}

fn pbl_u8(name: &str, value: u32) -> Result<u8, OnProbeError> {
    u8::try_from(value)
        .map_err(|_| OnProbeError::other(format!("cvitek-dwmac {name} value {value} exceeds u8")))
}

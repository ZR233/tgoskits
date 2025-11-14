use core::ffi::c_void;

mod protocol;

pub use protocol::console::SimpleTextOutputProtocol;

/// Handle to a UEFI entity (protocol, image, etc).
pub type Handle = *mut c_void;

/// The common header that all UEFI tables begin with.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[repr(C)]
pub struct Header {
    /// Unique identifier for this table.
    pub signature: u64,
    /// Revision of the spec this table conforms to.
    pub revision: u32,
    /// The size in bytes of the entire table.
    pub size: u32,
    /// 32-bit CRC-32-Castagnoli of the entire table,
    /// calculated with this field set to 0.
    pub crc: u32,
    /// Reserved field that must be set to 0.
    pub reserved: u32,
}

#[derive(Clone, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct SystemTable {
    pub header: Header,

    pub firmware_vendor: *const char,
    pub firmware_revision: u32,

    pub stdin_handle: Handle,
    pub stdin: *mut c_void,

    pub stdout_handle: Handle,
    pub stdout: *mut SimpleTextOutputProtocol,

    pub stderr_handle: Handle,
    pub stderr: *mut SimpleTextOutputProtocol,

    pub runtime_services: *mut c_void,
    pub boot_services: *mut c_void,

    pub number_of_configuration_table_entries: usize,
    pub configuration_table: *mut c_void,
}

/// ABI-compatible UEFI boolean.
///
/// This is similar to a `bool`, but allows values other than 0 or 1 to be
/// stored without it being undefined behavior.
///
/// Any non-zero value is treated as logically `true`.
#[derive(Copy, Clone, Debug, Default, PartialEq, Ord, PartialOrd, Eq, Hash)]
#[repr(transparent)]
pub struct Boolean(pub u8);

impl Boolean {
    /// [`Boolean`] representing `true`.
    pub const TRUE: Self = Self(1);

    /// [`Boolean`] representing `false`.
    pub const FALSE: Self = Self(0);
}

impl From<bool> for Boolean {
    fn from(value: bool) -> Self {
        match value {
            true => Self(1),
            false => Self(0),
        }
    }
}

impl From<Boolean> for bool {
    #[allow(clippy::match_like_matches_macro)]
    fn from(value: Boolean) -> Self {
        // We handle it as in C: Any bit-pattern != 0 equals true
        match value.0 {
            0 => false,
            _ => true,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(transparent)]
pub struct Status(usize);

impl Status {
    pub fn to_result(self) -> Result<(), Self> {
        if self.0 == 0 { Ok(()) } else { Err(self) }
    }
}

static mut SYSTEM_TABLE: usize = 0;

pub fn set_system_table_ptr(ptr: *const SystemTable) {
    unsafe {
        SYSTEM_TABLE = ptr as usize;
    }
}

pub fn system_table() -> Option<SystemTableGuard> {
    unsafe {
        if SYSTEM_TABLE == 0 {
            None
        } else {
            Some(SystemTableGuard(SYSTEM_TABLE as *mut SystemTable))
        }
    }
}

pub struct SystemTableGuard(*mut SystemTable);

unsafe impl Send for SystemTableGuard {}
unsafe impl Sync for SystemTableGuard {}

impl SystemTableGuard {
    fn as_mut(&mut self) -> &mut SystemTable {
        unsafe { &mut *self.0 }
    }

    pub fn stdout(&mut self) -> &'static mut SimpleTextOutputProtocol {
        unsafe { &mut *self.as_mut().stdout }
    }
}

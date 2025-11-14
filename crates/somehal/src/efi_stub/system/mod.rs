use crate::efi_stub::table::{self, SimpleTextOutputProtocol};

pub fn stdout() -> &'static mut SimpleTextOutputProtocol {
    table::system_table()
        .expect("System table not set")
        .stdout()
}

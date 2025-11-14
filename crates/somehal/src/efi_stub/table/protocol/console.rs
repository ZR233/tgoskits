use crate::efi_stub::table::{Boolean, Status};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct SimpleTextOutputMode {
    pub max_mode: i32,
    pub mode: i32,
    pub attribute: i32,
    pub cursor_column: i32,
    pub cursor_row: i32,
    pub cursor_visible: Boolean,
}

#[derive(Debug)]
#[repr(C)]
pub struct SimpleTextOutputProtocol {
    pub reset: unsafe extern "C" fn(this: *mut Self, extended: Boolean) -> Status,
    pub output_string: unsafe extern "C" fn(this: *mut Self, string: *const char) -> Status,
    pub test_string: unsafe extern "C" fn(this: *mut Self, string: *const char) -> Status,
    pub query_mode: unsafe extern "C" fn(
        this: *mut Self,
        mode: usize,
        columns: *mut usize,
        rows: *mut usize,
    ) -> Status,
    pub set_mode: unsafe extern "C" fn(this: *mut Self, mode: usize) -> Status,
    pub set_attribute: unsafe extern "C" fn(this: *mut Self, attribute: usize) -> Status,
    pub clear_screen: unsafe extern "C" fn(this: *mut Self) -> Status,
    pub set_cursor_position:
        unsafe extern "C" fn(this: *mut Self, column: usize, row: usize) -> Status,
    pub enable_cursor: unsafe extern "C" fn(this: *mut Self, visible: Boolean) -> Status,
    pub mode: *mut SimpleTextOutputMode,
}

// impl SimpleTextOutputProtocol {
//     pub const GUID: Guid = guid!("387477c2-69c7-11d2-8e39-00a0c969723b");
// }

impl SimpleTextOutputProtocol {
    pub fn write_str(&mut self, s: &str) -> Result<(), Status> {
        let mut iter = s.encode_utf16();
        loop {
            match iter.next_chunk::<256>() {
                Ok(chunk) => {
                    unsafe { (self.output_string)(self, chunk.as_ptr() as *const char) }
                        .to_result()?;
                }
                Err(remaining) => {
                    let mut buffer: [u16; 256] = [0; 256];
                    for (i, ch) in remaining.enumerate() {
                        buffer[i] = ch;
                    }

                    unsafe { (self.output_string)(self, buffer.as_ptr() as *const char) }
                        .to_result()?;
                    break;
                }
            }
        }
        Ok(())
    }
}

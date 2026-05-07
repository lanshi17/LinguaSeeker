mod error;
mod hash;
mod backends;
mod archive;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    Ok(())
}

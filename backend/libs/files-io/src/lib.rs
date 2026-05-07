mod error;
mod hash;
mod backends;
mod archive;
mod py;

use pyo3::prelude::*;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<py::file::File>()?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_compress, m)?)?;
    m.add_function(wrap_pyfunction!(py::parallel::parallel_copy_async, m)?)?;
    m.add_function(wrap_pyfunction!(py::dedup::check_duplicate, m)?)?;
    m.add_function(wrap_pyfunction!(py::dedup::batch_hash, m)?)?;
    Ok(())
}

use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let literature = PyModule::new(m.py(), "literature")?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::fetch_one, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::fetch_multi, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_web, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_html, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::extract_pdf_links, &literature
    )?)?;
    m.add_submodule(&literature)?;
    m.py()
        .import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item("rust_io.literature", &literature)?;

    let files = PyModule::new(m.py(), "files")?;
    files.add_class::<files_io::py::file::File>()?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_compress, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy_async, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::check_duplicate, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::batch_hash, &files
    )?)?;
    m.add_submodule(&files)?;
    m.py()
        .import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item("rust_io.files", &files)?;

    Ok(())
}

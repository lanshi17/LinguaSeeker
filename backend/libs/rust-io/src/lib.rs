use pyo3::prelude::*;
use pyo3::types::PyDict;

fn register_submodule(
    parent: &Bound<'_, PyModule>,
    full_name: &str,
    submodule: &Bound<'_, PyModule>,
) -> PyResult<()> {
    parent.add_submodule(submodule)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item(full_name, submodule)?;
    Ok(())
}

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let http = PyModule::new(m.py(), "http")?;
    http.add_function(wrap_pyfunction!(http_io::py::fetch_one, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::fetch_multi, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::scrape_web, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::scrape_html, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::extract_pdf_links, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::mineru_create_task, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::mineru_get_result, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::mineru_batch_submit, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::mineru_batch_result, &http)?)?;
    register_submodule(m, "rust_io.http", &http)?;

    let files = PyModule::new(m.py(), "files")?;
    files.add_class::<files_io::py::file::File>()?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_compress,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy_async,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::check_duplicate,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(files_io::py::dedup::batch_hash, &files)?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::utils::compute_sha256,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(files_io::py::utils::write_file, &files)?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::utils::validate_pdf_magic,
        &files
    )?)?;
    register_submodule(m, "rust_io.files", &files)?;

    Ok(())
}

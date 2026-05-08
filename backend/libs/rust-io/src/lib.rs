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
    let literature = PyModule::new(m.py(), "literature")?;
    literature.add_function(wrap_pyfunction!(literature_io::py::fetch_one, &literature)?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::fetch_multi,
        &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_web,
        &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_html,
        &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::extract_pdf_links,
        &literature
    )?)?;
    register_submodule(m, "rust_io.literature", &literature)?;

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

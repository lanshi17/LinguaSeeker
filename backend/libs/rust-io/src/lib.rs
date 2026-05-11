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
    let net = PyModule::new(m.py(), "net")?;
    net.add_function(wrap_pyfunction!(net_io::py::fetch_one, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::fetch_multi, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::scrape_web, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::scrape_html, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::extract_pdf_links, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::mineru_create_task, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::mineru_get_result, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::mineru_batch_submit, &net)?)?;
    net.add_function(wrap_pyfunction!(net_io::py::mineru_batch_result, &net)?)?;
    net.add_function(wrap_pyfunction!(
        net_io::py::mineru_create_upload_url,
        &net
    )?)?;
    net.add_function(wrap_pyfunction!(
        net_io::py::mineru_create_batch_upload_urls,
        &net
    )?)?;
    net.add_function(wrap_pyfunction!(
        net_io::py::mineru_upload_local_file,
        &net
    )?)?;
    net.add_function(wrap_pyfunction!(
        net_io::py::mineru_upload_local_files,
        &net
    )?)?;
    register_submodule(m, "rust_io.net", &net)?;

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

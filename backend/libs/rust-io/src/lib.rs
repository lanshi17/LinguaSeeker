mod error;
mod types;
mod client;
mod providers;
mod scraper;
mod py;
mod files;

use pyo3::prelude::*;

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let literature = PyModule::new(m.py(), "literature")?;
    
    literature.add_function(wrap_pyfunction!(py::fetch_one, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::fetch_multi, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::scrape_web, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::scrape_html, &literature)?)?;
    literature.add_function(wrap_pyfunction!(py::extract_pdf_links, &literature)?)?;
    
    m.add_submodule(&literature)?;

    let files_mod = PyModule::new(m.py(), "files")?;
    files_mod.add_function(wrap_pyfunction!(files::compute_sha256, &files_mod)?)?;
    files_mod.add_function(wrap_pyfunction!(files::write_file, &files_mod)?)?;
    files_mod.add_function(wrap_pyfunction!(files::validate_pdf_magic, &files_mod)?)?;
    m.add_submodule(&files_mod)?;

    Ok(())
}

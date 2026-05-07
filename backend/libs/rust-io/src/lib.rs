mod error;
mod types;
mod client;
mod providers;
mod scraper;
mod py;

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
    Ok(())
}

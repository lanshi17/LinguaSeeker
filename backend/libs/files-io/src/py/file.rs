use pyo3::prelude::*;

#[pyclass]
pub struct File;

#[pymethods]
impl File {
    #[new]
    fn new(_path: &str) -> PyResult<Self> {
        todo!()
    }
}

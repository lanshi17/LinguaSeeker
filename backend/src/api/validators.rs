//! Request parameter validation
//!
//! This module contains validators for API request parameters

use uuid::Uuid;

use crate::models::AppError;

/// Validate and parse a UUID from a string
pub fn validate_uuid(id: &str) -> Result<Uuid, AppError> {
    Uuid::parse_str(id)
        .map_err(|_| AppError::InvalidInput(format!("Invalid UUID format: {}", id)))
}

/// Validate that a string is not empty
pub fn validate_not_empty(value: &str, field_name: &str) -> Result<(), AppError> {
    if value.trim().is_empty() {
        return Err(AppError::InvalidInput(format!("{} cannot be empty", field_name)));
    }
    Ok(())
}

/// Validate file size (in bytes)
pub fn validate_file_size(size: usize, max_size: usize) -> Result<(), AppError> {
    if size > max_size {
        return Err(AppError::InvalidInput(format!(
            "File size {} exceeds maximum allowed size {}",
            size, max_size
        )));
    }
    Ok(())
}

/// Validate file extension
pub fn validate_file_extension(filename: &str, allowed_extensions: &[&str]) -> Result<(), AppError> {
    let extension = filename
        .rsplit('.')
        .next()
        .map(|s| s.to_lowercase())
        .unwrap_or_default();

    if !allowed_extensions.contains(&extension.as_str()) {
        return Err(AppError::InvalidInput(format!(
            "File extension '{}' is not allowed. Allowed extensions: {:?}",
            extension, allowed_extensions
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_uuid_valid() {
        let uuid_str = "550e8400-e29b-41d4-a716-446655440000";
        assert!(validate_uuid(uuid_str).is_ok());
    }

    #[test]
    fn test_validate_uuid_invalid() {
        let uuid_str = "not-a-valid-uuid";
        assert!(validate_uuid(uuid_str).is_err());
    }

    #[test]
    fn test_validate_not_empty_valid() {
        assert!(validate_not_empty("hello", "field").is_ok());
    }

    #[test]
    fn test_validate_not_empty_invalid() {
        assert!(validate_not_empty("", "field").is_err());
        assert!(validate_not_empty("   ", "field").is_err());
    }

    #[test]
    fn test_validate_file_size_valid() {
        assert!(validate_file_size(100, 1000).is_ok());
    }

    #[test]
    fn test_validate_file_size_invalid() {
        assert!(validate_file_size(2000, 1000).is_err());
    }

    #[test]
    fn test_validate_file_extension_valid() {
        assert!(validate_file_extension("document.pdf", &["pdf", "txt"]).is_ok());
    }

    #[test]
    fn test_validate_file_extension_invalid() {
        assert!(validate_file_extension("document.exe", &["pdf", "txt"]).is_err());
    }
}

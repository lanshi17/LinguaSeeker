//! Configuration module for the evidence platform
//!
//! Handles environment variables and application configuration
//!
//! This module follows a layered architecture:
//! - `settings.rs`: Configuration structure definitions
//! - `env.rs`: Environment variable processing

pub mod env;
pub mod settings;

// Re-export main types for convenience
pub use settings::{
    ClinVarConfig, Config, DatabaseConfig, LlmConfig, RedisConfig, ServerConfig,
};

impl Config {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self, std::env::VarError> {
        env::load_from_env()
    }
}

//! Configuration module for the evidence platform
//! 
//! Handles environment variables and application configuration

use std::env;

/// Application configuration
#[derive(Debug, Clone)]
pub struct Config {
    /// Server host address
    pub host: String,
    /// Server port
    pub port: u16,
    /// PostgreSQL database URL
    pub database_url: String,
    /// Redis URL
    pub redis_url: String,
    /// LLM API endpoint
    pub llm_api_url: String,
    /// LLM API key
    pub llm_api_key: String,
    /// ClinVar API key (optional)
    pub clinvar_api_key: Option<String>,
}

impl Config {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self, env::VarError> {
        Ok(Self {
            host: env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            port: env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()
                .unwrap_or(8080),
            database_url: env::var("DATABASE_URL")
                .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/evidence_platform".to_string()),
            redis_url: env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
            llm_api_url: env::var("LLM_API_URL")
                .unwrap_or_else(|_| "http://localhost:11434/api/generate".to_string()),
            llm_api_key: env::var("LLM_API_KEY").unwrap_or_default(),
            clinvar_api_key: env::var("CLINVAR_API_KEY").ok(),
        })
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            host: "0.0.0.0".to_string(),
            port: 8080,
            database_url: "postgres://postgres:postgres@localhost:5432/evidence_platform".to_string(),
            redis_url: "redis://localhost:6379".to_string(),
            llm_api_url: "http://localhost:11434/api/generate".to_string(),
            llm_api_key: String::new(),
            clinvar_api_key: None,
        }
    }
}

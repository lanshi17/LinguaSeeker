//! Environment variable processing for configuration

use std::env;
use super::settings::{
    ClinVarConfig, Config, DatabaseConfig, LlmConfig, RedisConfig, ServerConfig,
};

/// Load configuration from environment variables
pub fn load_from_env() -> Result<Config, env::VarError> {
    Ok(Config {
        server: load_server_config(),
        database: load_database_config(),
        redis: load_redis_config(),
        llm: load_llm_config(),
        clinvar: load_clinvar_config(),
    })
}

/// Load server configuration from environment
fn load_server_config() -> ServerConfig {
    ServerConfig {
        host: env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
        port: env::var("PORT")
            .unwrap_or_else(|_| "8080".to_string())
            .parse()
            .unwrap_or(8080),
    }
}

/// Load database configuration from environment
fn load_database_config() -> DatabaseConfig {
    DatabaseConfig {
        url: env::var("DATABASE_URL").unwrap_or_else(|_| {
            "postgres://postgres:postgres@localhost:5432/evidence_platform".to_string()
        }),
        max_connections: env::var("DATABASE_MAX_CONNECTIONS")
            .unwrap_or_else(|_| "10".to_string())
            .parse()
            .unwrap_or(10),
    }
}

/// Load Redis configuration from environment
fn load_redis_config() -> RedisConfig {
    RedisConfig {
        url: env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string()),
    }
}

/// Load LLM configuration from environment
fn load_llm_config() -> LlmConfig {
    LlmConfig {
        api_url: env::var("LLM_API_URL")
            .unwrap_or_else(|_| "http://localhost:11434/api/generate".to_string()),
        api_key: env::var("LLM_API_KEY").unwrap_or_default(),
        model: env::var("LLM_MODEL").unwrap_or_else(|_| "llama3.2".to_string()),
    }
}

/// Load ClinVar configuration from environment
fn load_clinvar_config() -> ClinVarConfig {
    ClinVarConfig {
        api_key: env::var("CLINVAR_API_KEY").ok(),
        base_url: env::var("CLINVAR_API_BASE_URL")
            .unwrap_or_else(|_| "https://eutils.ncbi.nlm.nih.gov/entrez/eutils".to_string()),
    }
}

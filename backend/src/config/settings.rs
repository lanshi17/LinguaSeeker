//! Configuration structures for the evidence platform

/// Application configuration
#[derive(Debug, Clone)]
pub struct Config {
    /// Server configuration
    pub server: ServerConfig,
    /// Database configuration
    pub database: DatabaseConfig,
    /// Redis cache configuration
    pub redis: RedisConfig,
    /// LLM API configuration
    pub llm: LlmConfig,
    /// ClinVar API configuration
    pub clinvar: ClinVarConfig,
}

/// Server configuration
#[derive(Debug, Clone)]
pub struct ServerConfig {
    /// Server host address
    pub host: String,
    /// Server port
    pub port: u16,
}

/// Database configuration
#[derive(Debug, Clone)]
pub struct DatabaseConfig {
    /// PostgreSQL database URL
    pub url: String,
    /// Maximum number of connections in the pool
    pub max_connections: u32,
}

/// Redis cache configuration
#[derive(Debug, Clone)]
pub struct RedisConfig {
    /// Redis URL
    pub url: String,
}

/// LLM API configuration
#[derive(Debug, Clone)]
pub struct LlmConfig {
    /// LLM API endpoint URL
    pub api_url: String,
    /// LLM API key
    pub api_key: String,
    /// Default model to use
    pub model: String,
}

/// ClinVar API configuration
#[derive(Debug, Clone)]
pub struct ClinVarConfig {
    /// ClinVar API key (optional, for higher rate limits)
    pub api_key: Option<String>,
    /// ClinVar API base URL
    pub base_url: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            server: ServerConfig::default(),
            database: DatabaseConfig::default(),
            redis: RedisConfig::default(),
            llm: LlmConfig::default(),
            clinvar: ClinVarConfig::default(),
        }
    }
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            host: "0.0.0.0".to_string(),
            port: 8080,
        }
    }
}

impl Default for DatabaseConfig {
    fn default() -> Self {
        Self {
            url: "postgres://postgres:postgres@localhost:5432/evidence_platform".to_string(),
            max_connections: 10,
        }
    }
}

impl Default for RedisConfig {
    fn default() -> Self {
        Self {
            url: "redis://localhost:6379".to_string(),
        }
    }
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            api_url: "http://localhost:11434/api/generate".to_string(),
            api_key: String::new(),
            model: "llama3.2".to_string(),
        }
    }
}

impl Default for ClinVarConfig {
    fn default() -> Self {
        Self {
            api_key: None,
            base_url: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils".to_string(),
        }
    }
}

//! Language support models

use serde::{Deserialize, Serialize};

/// Supported languages for document parsing
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Chinese,
    Japanese,
    German,
    French,
    English,
}

impl std::fmt::Display for Language {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Language::Chinese => write!(f, "chinese"),
            Language::Japanese => write!(f, "japanese"),
            Language::German => write!(f, "german"),
            Language::French => write!(f, "french"),
            Language::English => write!(f, "english"),
        }
    }
}

impl std::str::FromStr for Language {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "chinese" | "zh" | "中文" => Ok(Language::Chinese),
            "japanese" | "ja" | "日本語" => Ok(Language::Japanese),
            "german" | "de" | "deutsch" => Ok(Language::German),
            "french" | "fr" | "français" => Ok(Language::French),
            "english" | "en" => Ok(Language::English),
            _ => Err(format!("Unknown language: {}", s)),
        }
    }
}

//! Variant classification models and ACMG/AMP criteria

use serde::{Deserialize, Serialize};

/// ACMG/AMP variant classification categories
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VariantClassification {
    Pathogenic,
    LikelyPathogenic,
    UncertainSignificance,
    LikelyBenign,
    Benign,
}

impl std::fmt::Display for VariantClassification {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VariantClassification::Pathogenic => write!(f, "Pathogenic"),
            VariantClassification::LikelyPathogenic => write!(f, "Likely Pathogenic"),
            VariantClassification::UncertainSignificance => write!(f, "Uncertain Significance"),
            VariantClassification::LikelyBenign => write!(f, "Likely Benign"),
            VariantClassification::Benign => write!(f, "Benign"),
        }
    }
}

/// ACMG/AMP evidence criteria
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcmgCriteria {
    /// Very strong pathogenic criteria (PVS1)
    pub pvs1: bool,
    /// Strong pathogenic criteria (PS1-PS4)
    pub ps: Vec<String>,
    /// Moderate pathogenic criteria (PM1-PM6)
    pub pm: Vec<String>,
    /// Supporting pathogenic criteria (PP1-PP5)
    pub pp: Vec<String>,
    /// Stand-alone benign criteria (BA1)
    pub ba1: bool,
    /// Strong benign criteria (BS1-BS4)
    pub bs: Vec<String>,
    /// Supporting benign criteria (BP1-BP7)
    pub bp: Vec<String>,
}

impl Default for AcmgCriteria {
    fn default() -> Self {
        Self {
            pvs1: false,
            ps: Vec::new(),
            pm: Vec::new(),
            pp: Vec::new(),
            ba1: false,
            bs: Vec::new(),
            bp: Vec::new(),
        }
    }
}

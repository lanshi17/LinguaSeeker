/**
 * Demo knowledge graph shown as a placeholder while the backend loads or
 * when the graph is empty (e.g. production Neo4j hasn't been seeded yet).
 *
 * The demo mirrors the real graph shape — a gene with related diseases,
 * phenotypes, and a few evidence bridges — so the canvas looks alive before
 * real data arrives. Keep it small and visually representative.
 */

import type { KnowledgeGraph } from "../types/graphRag";

export const DEMO_GRAPH_GENE = "EGFR";

export const demoKnowledgeGraph: KnowledgeGraph = {
  nodes: [
    {
      node_id: "gene:EGFR",
      labels: ["Gene"],
      display_name: "EGFR",
      properties: {
        source_db: "HGNC",
        external_id: "3236",
      },
    },
    {
      node_id: "disease:MONDO:0008903",
      labels: ["Disease"],
      display_name: "Non-small cell lung carcinoma",
      properties: {
        source_db: "MONDO",
        external_id: "MONDO:0008903",
      },
    },
    {
      node_id: "disease:OMIM:131220",
      labels: ["Disease"],
      display_name: "Glioblastoma multiforme",
      properties: {
        source_db: "OMIM",
        external_id: "OMIM:131220",
      },
    },
    {
      node_id: "phenotype:HP:0002098",
      labels: ["Phenotype"],
      display_name: "Short stature",
      properties: {
        source_db: "HPO",
        external_id: "HP:0002098",
      },
    },
    {
      node_id: "phenotype:HP:0001250",
      labels: ["Phenotype"],
      display_name: "Seizure",
      properties: {
        source_db: "HPO",
        external_id: "HP:0001250",
      },
    },
    {
      node_id: "evidence:demo-pubmed-1",
      labels: ["EvidenceDoc"],
      display_name: "EGFR mutations in NSCLC (demo)",
      properties: {
        pmid: "DEMO-1",
        evidence_count: 42,
      },
    },
    {
      node_id: "evidence:demo-pubmed-2",
      labels: ["EvidenceDoc"],
      display_name: "Glioma EGFR amplification (demo)",
      properties: {
        pmid: "DEMO-2",
        evidence_count: 18,
      },
    },
  ],
  edges: [
    {
      source_id: "gene:EGFR",
      target_id: "disease:MONDO:0008903",
      rel_type: "ASSOC_STRONG",
      properties: {
        relationship_type: "gene_associated_with_disease",
        source_db: "ClinGen",
        evidence_level: "strong",
        evidence_count: 42,
      },
    },
    {
      source_id: "gene:EGFR",
      target_id: "disease:OMIM:131220",
      rel_type: "ASSOC_MODERATE",
      properties: {
        relationship_type: "gene_associated_with_disease",
        source_db: "ClinGen",
        evidence_level: "moderate",
        evidence_count: 18,
      },
    },
    {
      source_id: "gene:EGFR",
      target_id: "phenotype:HP:0002098",
      rel_type: "HAS_PHENOTYPE",
      properties: {
        relationship_type: "phenotype_associated_with_gene",
        source_db: "HPO",
      },
    },
    {
      source_id: "gene:EGFR",
      target_id: "phenotype:HP:0001250",
      rel_type: "HAS_PHENOTYPE",
      properties: {
        relationship_type: "phenotype_associated_with_gene",
        source_db: "HPO",
      },
    },
    {
      source_id: "evidence:demo-pubmed-1",
      target_id: "gene:EGFR",
      rel_type: "SUPPORTS",
      properties: { role: "subject" },
    },
    {
      source_id: "evidence:demo-pubmed-1",
      target_id: "disease:MONDO:0008903",
      rel_type: "SUPPORTS",
      properties: { role: "object" },
    },
    {
      source_id: "evidence:demo-pubmed-2",
      target_id: "gene:EGFR",
      rel_type: "SUPPORTS",
      properties: { role: "subject" },
    },
    {
      source_id: "evidence:demo-pubmed-2",
      target_id: "disease:OMIM:131220",
      rel_type: "SUPPORTS",
      properties: { role: "object" },
    },
  ],
};

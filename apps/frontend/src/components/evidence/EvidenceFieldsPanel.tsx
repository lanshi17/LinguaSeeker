import { useState } from 'react';

import type {
  ControlInfo,
  DiseaseInfo,
  EvidenceRecord,
  EvidenceSearchData,
  ExperimentData,
  ExtractedEvidenceFields,
  GeneInfo,
  PedigreeInfo,
  PhenotypeInfo,
  ReferenceGenomeInfo,
  SpeciesInfo,
  TranscriptInfo,
  VariantInfo,
} from '../../types/evidence';

// ==================== Helpers ====================

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asEvidenceSearchData(data: unknown): EvidenceSearchData | null {
  if (!isRecord(data)) return null;
  return data as EvidenceSearchData;
}

function confidenceBadgeStyle(confidence: number): React.CSSProperties {
  const color =
    confidence >= 85
      ? 'var(--success)'
      : confidence >= 60
        ? 'var(--warning)'
        : 'var(--muted)';
  return {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 700,
    border: `1px solid ${color}`,
    color,
    marginLeft: 6,
  };
}

function validBadge(isValid: string | null | undefined) {
  if (isValid === 'true') {
    return (
      <span style={{ color: 'var(--success)', fontSize: 11, fontWeight: 700, marginLeft: 6 }}>
        ✓ Valid
      </span>
    );
  }
  return (
    <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 6 }}>
      ✗ Invalid
    </span>
  );
}

// ==================== Field sub-renderers ====================

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '') return null;
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 3 }}>
      <span style={{ color: 'var(--muted)', fontSize: 12, minWidth: 160, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ fontSize: 12 }}>{value}</span>
    </div>
  );
}

function QuoteRow({ quote }: { quote: string | null | undefined }) {
  if (!quote) return null;
  return (
    <div
      style={{
        fontSize: 11,
        color: 'var(--muted)',
        fontStyle: 'italic',
        marginTop: 3,
        borderLeft: '2px solid var(--border)',
        paddingLeft: 8,
      }}
    >
      &ldquo;{quote}&rdquo;
    </div>
  );
}

function renderGene(gene: GeneInfo) {
  return (
    <div>
      <FieldRow label="Symbol" value={gene.symbol} />
      <FieldRow label="Full name" value={gene.full_name} />
      <FieldRow label="NCBI Gene ID" value={gene.ncbi_gene_id} />
      <FieldRow label="Ensembl ID" value={gene.ensembl_id} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(gene.confidence)}>{gene.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={gene.evidence_quote} />
    </div>
  );
}

function renderTranscript(t: TranscriptInfo) {
  return (
    <div>
      <FieldRow label="Transcript ID" value={t.transcript_id} />
      <FieldRow label="Source" value={t.source} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(t.confidence)}>{t.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={t.evidence_quote} />
    </div>
  );
}

function renderRefGenome(r: ReferenceGenomeInfo) {
  return (
    <div>
      <FieldRow label="Version" value={r.version} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(r.confidence)}>{r.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={r.evidence_quote} />
    </div>
  );
}

function renderExperiment(e: ExperimentData) {
  return (
    <div>
      <FieldRow label="Assay type" value={e.assay_type} />
      <FieldRow label="Method" value={e.method_description} />
      <FieldRow label="Sample size" value={e.sample_size} />
      <FieldRow label="Cell line" value={e.cell_line} />
      <FieldRow label="Model organism" value={e.model_organism} />
      {e.key_findings && e.key_findings.length > 0 && (
        <div style={{ marginBottom: 3 }}>
          <span style={{ color: 'var(--muted)', fontSize: 12, display: 'block' }}>Key findings</span>
          <ul style={{ margin: '2px 0 2px 16px', padding: 0, fontSize: 12 }}>
            {e.key_findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(e.confidence)}>{e.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={e.evidence_quote} />
    </div>
  );
}

function renderDisease(d: DiseaseInfo, label: string) {
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginBottom: 3 }}>
        {label}
      </div>
      <FieldRow label="Disease name" value={d.disease_name} />
      <FieldRow label="CHPO ID" value={d.chpo_id} />
      <FieldRow label="ICD-10" value={d.icd10_code} />
      <FieldRow label="OMIM ID" value={d.omim_id} />
      <FieldRow label="Inheritance" value={d.inheritance_pattern} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(d.confidence)}>{d.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={d.evidence_quote} />
    </div>
  );
}

function renderSpecies(s: SpeciesInfo) {
  return (
    <div>
      <FieldRow label="Species" value={s.species_name} />
      <FieldRow label="Is human" value={s.is_human ? 'Yes' : 'No'} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(s.confidence)}>{s.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={s.evidence_quote} />
    </div>
  );
}

function renderPhenotype(p: PhenotypeInfo) {
  return (
    <div>
      <FieldRow label="Description" value={p.phenotype_description} />
      <FieldRow label="HPO IDs" value={p.hpo_ids?.join(', ')} />
      <FieldRow label="Severity" value={p.severity} />
      <FieldRow label="Onset age" value={p.onset_age} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(p.confidence)}>{p.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={p.evidence_quote} />
    </div>
  );
}

function renderVariant(v: VariantInfo) {
  return (
    <div>
      <FieldRow label="HGVS c." value={v.hgvs_c} />
      <FieldRow label="HGVS p." value={v.hgvs_p} />
      <FieldRow label="HGVS g." value={v.hgvs_g} />
      <FieldRow label="Chromosome" value={v.chromosome} />
      <FieldRow label="Position" value={v.position != null ? String(v.position) : null} />
      <FieldRow label="Ref allele" value={v.ref_allele} />
      <FieldRow label="Alt allele" value={v.alt_allele} />
      <FieldRow label="Variant type" value={v.variant_type} />
      <FieldRow label="dbSNP rs ID" value={v.rs_id} />
      <FieldRow label="ClinVar ID" value={v.clinvar_id} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(v.confidence)}>{v.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={v.evidence_quote} />
    </div>
  );
}

function renderControl(c: ControlInfo) {
  return (
    <div>
      <FieldRow label="Negative control" value={c.has_negative_control ? 'Yes' : 'No'} />
      <FieldRow
        label="Negative control desc."
        value={c.negative_control_description}
      />
      <FieldRow label="Positive control" value={c.has_positive_control ? 'Yes' : 'No'} />
      <FieldRow
        label="Positive control desc."
        value={c.positive_control_description}
      />
      <FieldRow label="Total control count" value={String(c.total_control_count)} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(c.confidence)}>{c.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={c.evidence_quote} />
    </div>
  );
}

function renderPedigree(p: PedigreeInfo) {
  return (
    <div>
      <FieldRow label="Has pedigree" value={p.has_pedigree ? 'Yes' : 'No'} />
      <FieldRow label="Family size" value={p.family_size != null ? String(p.family_size) : null} />
      <FieldRow
        label="Affected count"
        value={p.affected_count != null ? String(p.affected_count) : null}
      />
      <FieldRow label="Segregation data" value={p.segregation_data} />
      <FieldRow label="Inheritance pattern" value={p.inheritance_pattern} />
      <FieldRow
        label="Confidence"
        value={<span style={confidenceBadgeStyle(p.confidence)}>{p.confidence.toFixed(1)}</span>}
      />
      <QuoteRow quote={p.evidence_quote} />
    </div>
  );
}

// ==================== ExtractedFields section ====================

type FieldSection = {
  key: keyof ExtractedEvidenceFields;
  label: string;
  render: (val: unknown) => React.ReactNode;
};

const FIELD_SECTIONS: FieldSection[] = [
  { key: 'gene', label: 'Gene', render: (v) => renderGene(v as GeneInfo) },
  { key: 'transcript_id', label: 'Transcript', render: (v) => renderTranscript(v as TranscriptInfo) },
  {
    key: 'reference_genome_version',
    label: 'Reference Genome',
    render: (v) => renderRefGenome(v as ReferenceGenomeInfo),
  },
  { key: 'experiment_data', label: 'Experiment Data', render: (v) => renderExperiment(v as ExperimentData) },
  {
    key: 'disease_chpo',
    label: 'Disease (CHPO)',
    render: (v) => renderDisease(v as DiseaseInfo, 'CHPO'),
  },
  {
    key: 'disease_icd10',
    label: 'Disease (ICD-10)',
    render: (v) => renderDisease(v as DiseaseInfo, 'ICD-10'),
  },
  { key: 'species', label: 'Species', render: (v) => renderSpecies(v as SpeciesInfo) },
  { key: 'phenotype', label: 'Phenotype', render: (v) => renderPhenotype(v as PhenotypeInfo) },
  { key: 'variant', label: 'Variant', render: (v) => renderVariant(v as VariantInfo) },
  {
    key: 'negative_positive_control',
    label: 'Controls',
    render: (v) => renderControl(v as ControlInfo),
  },
  {
    key: 'pedigree_information',
    label: 'Pedigree',
    render: (v) => renderPedigree(v as PedigreeInfo),
  },
];

function ExtractedFieldsSection({ fields }: { fields: ExtractedEvidenceFields }) {
  const presentFields = FIELD_SECTIONS.filter((s) => fields[s.key] != null);
  const missingFields = FIELD_SECTIONS.filter((s) => fields[s.key] == null);

  if (presentFields.length === 0) {
    return <div className="muted" style={{ fontSize: 12 }}>No structured fields extracted.</div>;
  }

  return (
    <div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 10,
        }}
      >
        {presentFields.map((section) => (
          <div
            key={section.key}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: 10,
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 12,
                color: 'var(--brand)',
                marginBottom: 6,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {section.label}
            </div>
            {section.render(fields[section.key])}
          </div>
        ))}
      </div>
      {missingFields.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span className="muted" style={{ fontSize: 11 }}>
            Not extracted:{' '}
            {missingFields.map((s) => s.label).join(', ')}
          </span>
        </div>
      )}
    </div>
  );
}

// ==================== Evidence Record card ====================

function EvidenceRecordCard({ record, index }: { record: EvidenceRecord; index: number }) {
  const [expanded, setExpanded] = useState(false);

  const title =
    record.gene_symbol ??
    record.variant_hgvs_c ??
    `Evidence #${record.evidence_id ?? index + 1}`;

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 12,
      }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          padding: '10px 14px',
          background: 'rgba(255,255,255,0.04)',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text)',
          textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700 }}>{title}</span>
          {record.variant_hgvs_c && record.gene_symbol && (
            <span className="muted" style={{ fontSize: 12 }}>
              {record.variant_hgvs_c}
            </span>
          )}
          {record.evidence_classification && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: '1px 8px',
                borderRadius: 999,
                background: 'rgba(124,92,255,0.2)',
                color: 'var(--brand)',
              }}
            >
              {record.evidence_classification}
            </span>
          )}
          {record.evidence_strength && (
            <span className="muted" style={{ fontSize: 11 }}>
              {record.evidence_strength}
            </span>
          )}
          {record.overall_confidence != null && (
            <span style={confidenceBadgeStyle(record.overall_confidence)}>
              {record.overall_confidence.toFixed(1)}%
            </span>
          )}
          {validBadge(record.is_valid)}
        </div>
        <span style={{ fontSize: 14, color: 'var(--muted)', flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {/* Body */}
      {expanded && (
        <div style={{ padding: '12px 14px' }}>
          {/* Summary row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: 6,
              marginBottom: 14,
              fontSize: 12,
            }}
          >
            {record.gene_symbol && <FieldRow label="Gene" value={record.gene_symbol} />}
            {record.variant_hgvs_c && <FieldRow label="HGVS c." value={record.variant_hgvs_c} />}
            {record.variant_hgvs_p && <FieldRow label="HGVS p." value={record.variant_hgvs_p} />}
            {record.protein_change && (
              <FieldRow label="Protein change" value={record.protein_change} />
            )}
            {record.transcript_id && (
              <FieldRow label="Transcript ID" value={record.transcript_id} />
            )}
            {record.reference_genome && (
              <FieldRow label="Ref. genome" value={record.reference_genome} />
            )}
            {record.disease_name && <FieldRow label="Disease" value={record.disease_name} />}
            {record.icd10_code && <FieldRow label="ICD-10" value={record.icd10_code} />}
            {record.species && <FieldRow label="Species" value={record.species} />}
            {record.phenotype && <FieldRow label="Phenotype" value={record.phenotype} />}
            {record.acmg_levels && record.acmg_levels.length > 0 && (
              <FieldRow label="ACMG levels" value={record.acmg_levels.join(', ')} />
            )}
          </div>

          {/* Extracted fields */}
          {record.extracted_fields ? (
            <div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 13,
                  marginBottom: 8,
                  color: 'var(--text)',
                }}
              >
                Extracted Fields
              </div>
              <ExtractedFieldsSection fields={record.extracted_fields} />
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 12 }}>
              No extracted fields available for this record.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== Main panel ====================

type Props = {
  data: unknown;
};

export function EvidenceFieldsPanel({ data }: Props) {
  const parsed = asEvidenceSearchData(data);

  if (!parsed) {
    return (
      <div className="muted" style={{ fontSize: 13 }}>
        No evidence data available.
      </div>
    );
  }

  const records = parsed.evidence_records ?? [];

  if (records.length === 0) {
    return (
      <div>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Evidence Records</div>
        <div className="muted" style={{ fontSize: 13 }}>
          No evidence records found for this document.
        </div>
        {parsed.total_evidence === 0 && (
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            The document may not have been fully processed yet.
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <div style={{ fontWeight: 700 }}>
          Evidence Records
          <span className="muted" style={{ fontWeight: 400, fontSize: 13, marginLeft: 8 }}>
            {records.length} record{records.length !== 1 ? 's' : ''} from{' '}
            {parsed.document_count ?? 1} document{(parsed.document_count ?? 1) !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {records.map((record, i) => (
        <EvidenceRecordCard key={record.evidence_id ?? i} record={record} index={i} />
      ))}
    </div>
  );
}

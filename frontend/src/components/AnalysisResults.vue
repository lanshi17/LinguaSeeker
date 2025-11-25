<script setup lang="ts">
import { computed } from 'vue';
import type { AnalysisResult, ClinVarResult } from '@/types';

const props = defineProps<{
  result: AnalysisResult;
}>();

const clinvarMatchCount = computed(() => {
  return props.result.clinvar_results.filter(r => r.clinvar_id).length;
});

function getClassificationClass(classification: string | null): string {
  if (!classification) return '';
  const lower = classification.toLowerCase();
  if (lower === 'pathogenic') return 'classification-pathogenic';
  if (lower === 'likely pathogenic') return 'classification-likely-pathogenic';
  if (lower.includes('uncertain')) return 'classification-uncertain';
  if (lower === 'likely benign') return 'classification-likely-benign';
  if (lower === 'benign') return 'classification-benign';
  return '';
}

function getClinVarResult(variantId: string): ClinVarResult | undefined {
  return props.result.clinvar_results.find(r => r.variant_id === variantId);
}
</script>

<template>
  <div class="card">
    <h2>🔬 Analysis Results</h2>

    <!-- Summary Statistics -->
    <div class="summary-stats">
      <div class="stat-item">
        <div class="stat-value">{{ result.evidence.length }}</div>
        <div class="stat-label">Variants Found</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ clinvarMatchCount }}</div>
        <div class="stat-label">ClinVar Matches</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ (result.confidence_score * 100).toFixed(0) }}%</div>
        <div class="stat-label">Confidence</div>
      </div>
      <div v-if="result.final_classification" class="stat-item">
        <div :class="'classification-badge ' + getClassificationClass(result.final_classification)">
          {{ result.final_classification }}
        </div>
        <div class="stat-label">Final Classification</div>
      </div>
    </div>

    <!-- Confidence Meter -->
    <div class="confidence-meter">
      <div 
        class="confidence-fill" 
        :style="{ width: (result.confidence_score * 100) + '%' }"
      ></div>
    </div>

    <!-- Evidence Cards -->
    <div class="results-section">
      <h3>Extracted Evidence</h3>
      
      <div v-for="evidence in result.evidence" :key="evidence.id" class="evidence-card">
        <div class="evidence-header">
          <div>
            <span class="gene-name">{{ evidence.gene }}</span>
            <span v-if="evidence.transcript" class="transcript">
              {{ evidence.transcript }}
            </span>
          </div>
          <span 
            v-if="evidence.suggested_classification"
            :class="'classification-badge ' + getClassificationClass(evidence.suggested_classification)"
          >
            {{ evidence.suggested_classification }}
          </span>
        </div>

        <div v-if="evidence.hgvs_c || evidence.hgvs_p" class="hgvs-notation">
          <code v-if="evidence.hgvs_c">{{ evidence.hgvs_c }}</code>
          <code v-if="evidence.hgvs_p">{{ evidence.hgvs_p }}</code>
        </div>

        <!-- ACMG Criteria -->
        <div class="acmg-criteria">
          <span v-if="evidence.acmg_criteria.pvs1" class="criteria-tag criteria-pathogenic">PVS1</span>
          <span v-for="ps in evidence.acmg_criteria.ps" :key="ps" class="criteria-tag criteria-pathogenic">{{ ps }}</span>
          <span v-for="pm in evidence.acmg_criteria.pm" :key="pm" class="criteria-tag criteria-pathogenic">{{ pm }}</span>
          <span v-for="pp in evidence.acmg_criteria.pp" :key="pp" class="criteria-tag criteria-pathogenic">{{ pp }}</span>
          <span v-if="evidence.acmg_criteria.ba1" class="criteria-tag criteria-benign">BA1</span>
          <span v-for="bs in evidence.acmg_criteria.bs" :key="bs" class="criteria-tag criteria-benign">{{ bs }}</span>
          <span v-for="bp in evidence.acmg_criteria.bp" :key="bp" class="criteria-tag criteria-benign">{{ bp }}</span>
        </div>

        <div class="evidence-text">
          <strong>Evidence:</strong> {{ evidence.evidence_text }}
        </div>

        <!-- ClinVar Info -->
        <div v-if="getClinVarResult(evidence.variant_id)" class="clinvar-info">
          <h4>ClinVar Validation</h4>
          <template v-if="getClinVarResult(evidence.variant_id)?.clinvar_id">
            <p><strong>ClinVar ID:</strong> {{ getClinVarResult(evidence.variant_id)?.clinvar_id }}</p>
            <p v-if="getClinVarResult(evidence.variant_id)?.classification">
              <strong>ClinVar Classification:</strong> 
              {{ getClinVarResult(evidence.variant_id)?.classification }}
            </p>
            <p v-if="getClinVarResult(evidence.variant_id)?.review_status">
              <strong>Review Status:</strong> 
              {{ getClinVarResult(evidence.variant_id)?.review_status }}
            </p>
          </template>
          <div v-else class="not-found">
            Variant not found in ClinVar
          </div>
        </div>

        <div class="evidence-confidence">
          Confidence: {{ (evidence.confidence_score * 100).toFixed(0) }}%
        </div>
      </div>

      <div v-if="result.evidence.length === 0" class="empty-state">
        No variants found in the document.
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 24px;
  margin-bottom: 24px;
}

.card h2 {
  font-size: 1.25rem;
  margin-bottom: 16px;
  color: #1f2937;
  border-bottom: 2px solid #2563eb;
  padding-bottom: 8px;
}

.summary-stats {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #2563eb;
}

.stat-label {
  font-size: 0.85rem;
  color: #6b7280;
  margin-top: 4px;
}

.confidence-meter {
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 24px;
}

.confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #059669, #2563eb);
  transition: width 0.5s ease;
}

.results-section h3 {
  margin-bottom: 16px;
  font-size: 1.1rem;
}

.evidence-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.gene-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: #2563eb;
}

.transcript {
  color: #6b7280;
  margin-left: 8px;
}

.hgvs-notation {
  margin-top: 8px;
}

.hgvs-notation code {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 8px;
}

.classification-badge {
  padding: 6px 16px;
  border-radius: 20px;
  font-weight: 500;
  font-size: 0.9rem;
}

.classification-pathogenic { background: #fee2e2; color: #991b1b; }
.classification-likely-pathogenic { background: #ffedd5; color: #9a3412; }
.classification-uncertain { background: #fef3c7; color: #92400e; }
.classification-likely-benign { background: #d1fae5; color: #065f46; }
.classification-benign { background: #cffafe; color: #0e7490; }

.acmg-criteria {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.criteria-tag {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 500;
}

.criteria-pathogenic { background: #fecaca; color: #991b1b; }
.criteria-benign { background: #a7f3d0; color: #065f46; }

.evidence-text {
  margin-top: 12px;
  padding: 12px;
  background: white;
  border-radius: 6px;
  font-size: 0.9rem;
  color: #6b7280;
}

.clinvar-info {
  margin-top: 12px;
  padding: 12px;
  background: #eff6ff;
  border-radius: 6px;
}

.clinvar-info h4 {
  font-size: 0.9rem;
  margin-bottom: 8px;
  color: #2563eb;
}

.clinvar-info p {
  margin: 4px 0;
  font-size: 0.9rem;
}

.clinvar-info .not-found {
  color: #6b7280;
  font-style: italic;
}

.evidence-confidence {
  margin-top: 12px;
  color: #6b7280;
  font-size: 0.85rem;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { Document } from '@/types';
import { languageDisplayNames } from '@/types';
import { listDocuments, analyzeDocument, getAnalysisResults } from '@/api';
import type { AnalysisResult, Language } from '@/types';

const emit = defineEmits<{
  (e: 'results', result: AnalysisResult): void;
}>();

const documents = ref<Document[]>([]);
const isLoading = ref(false);
const analyzingId = ref<string | null>(null);
const errorMessage = ref('');

async function loadDocuments() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const response = await listDocuments();
    documents.value = response.documents;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load documents';
  } finally {
    isLoading.value = false;
  }
}

async function handleAnalyze(id: string) {
  analyzingId.value = id;
  errorMessage.value = '';
  try {
    const result = await analyzeDocument(id);
    emit('results', result);
    await loadDocuments(); // Refresh the list
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Analysis failed';
  } finally {
    analyzingId.value = null;
  }
}

async function handleViewResults(id: string) {
  try {
    const result = await getAnalysisResults(id);
    emit('results', result);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load results';
  }
}

function formatLanguage(lang: string): string {
  return languageDisplayNames[lang as Language] || lang;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString();
}

// Expose refresh method for parent component
defineExpose({ loadDocuments });

onMounted(() => {
  loadDocuments();
});
</script>

<template>
  <div class="card">
    <h2>📚 Documents</h2>

    <div v-if="isLoading" class="loading">
      <div class="spinner"></div>
      <p>Loading documents...</p>
    </div>

    <div v-else-if="documents.length === 0" class="empty-state">
      <p>No documents uploaded yet. Upload a PDF to get started!</p>
    </div>

    <table v-else class="documents-table">
      <thead>
        <tr>
          <th>Filename</th>
          <th>Language</th>
          <th>Uploaded</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in documents" :key="doc.id">
          <td>{{ doc.filename }}</td>
          <td>{{ formatLanguage(doc.language) }}</td>
          <td>{{ formatDate(doc.upload_time) }}</td>
          <td>
            <span :class="'status-badge status-' + doc.status">
              {{ doc.status }}
            </span>
          </td>
          <td>
            <button 
              class="btn btn-primary"
              @click="handleAnalyze(doc.id)"
              :disabled="doc.status === 'processing' || analyzingId !== null"
            >
              {{ analyzingId === doc.id ? 'Analyzing...' : 'Analyze' }}
            </button>
            <button 
              v-if="doc.status === 'processed'"
              class="btn btn-success"
              @click="handleViewResults(doc.id)"
            >
              View Results
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
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

.loading {
  text-align: center;
  padding: 40px;
}

.spinner {
  border: 4px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.documents-table {
  width: 100%;
  border-collapse: collapse;
}

.documents-table th,
.documents-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}

.documents-table th {
  background: #f3f4f6;
  font-weight: 600;
}

.documents-table tr:hover {
  background: #f9fafb;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-uploaded { background: #dbeafe; color: #1e40af; }
.status-processing { background: #fef3c7; color: #92400e; }
.status-processed { background: #d1fae5; color: #065f46; }
.status-failed { background: #fee2e2; color: #991b1b; }

.btn {
  display: inline-block;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-right: 8px;
}

.btn-primary {
  background: #2563eb;
  color: white;
}

.btn-primary:hover {
  background: #1d4ed8;
}

.btn-success {
  background: #059669;
  color: white;
}

.btn-success:hover {
  background: #047857;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  color: #dc2626;
  margin-top: 12px;
}
</style>

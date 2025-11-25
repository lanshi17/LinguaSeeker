<script setup lang="ts">
import { ref } from 'vue';
import DocumentUpload from './components/DocumentUpload.vue';
import DocumentList from './components/DocumentList.vue';
import AnalysisResults from './components/AnalysisResults.vue';
import type { AnalysisResult } from './types';

const documentList = ref<InstanceType<typeof DocumentList> | null>(null);
const analysisResults = ref<AnalysisResult | null>(null);

function handleUploadComplete() {
  documentList.value?.loadDocuments();
}

function handleResults(result: AnalysisResult) {
  analysisResults.value = result;
}
</script>

<template>
  <div class="app">
    <header>
      <div class="container">
        <h1>🧬 Multilingual Document Evidence Collection Platform</h1>
        <p>ACMG/AMP Variant Classification with LLM Analysis and ClinVar Integration</p>
      </div>
    </header>

    <main class="container">
      <DocumentUpload @uploaded="handleUploadComplete" />
      <DocumentList ref="documentList" @results="handleResults" />
      <AnalysisResults v-if="analysisResults" :result="analysisResults" />
    </main>

    <footer class="container">
      <p>
        Multilingual Document Evidence Collection Platform - 
        Supporting Chinese, Japanese, German, French, and English documents
      </p>
    </footer>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #f3f4f6;
  color: #1f2937;
  line-height: 1.6;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  padding: 20px 0;
  margin-bottom: 30px;
}

header h1 {
  font-size: 1.8rem;
  margin-bottom: 5px;
}

header p {
  opacity: 0.9;
  font-size: 0.95rem;
}

footer {
  margin-top: 40px;
  padding: 20px;
  text-align: center;
  color: #6b7280;
  border-top: 1px solid #e5e7eb;
}
</style>

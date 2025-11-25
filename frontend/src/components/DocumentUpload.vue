<script setup lang="ts">
import { ref } from 'vue';
import type { Language } from '@/types';
import { languageDisplayNames } from '@/types';
import { uploadDocument } from '@/api';

const emit = defineEmits<{
  (e: 'uploaded'): void;
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const selectedLanguage = ref<Language>('english');
const isDragging = ref(false);
const isUploading = ref(false);
const errorMessage = ref('');

const languages: Language[] = ['english', 'chinese', 'japanese', 'german', 'french'];

function triggerFileInput() {
  fileInput.value?.click();
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
    errorMessage.value = '';
  }
}

function handleDragOver(event: DragEvent) {
  event.preventDefault();
  isDragging.value = true;
}

function handleDragLeave() {
  isDragging.value = false;
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  isDragging.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    selectedFile.value = event.dataTransfer.files[0];
    errorMessage.value = '';
  }
}

async function handleUpload() {
  if (!selectedFile.value) return;

  isUploading.value = true;
  errorMessage.value = '';

  try {
    await uploadDocument(selectedFile.value, selectedLanguage.value);
    selectedFile.value = null;
    if (fileInput.value) {
      fileInput.value.value = '';
    }
    emit('uploaded');
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Upload failed';
  } finally {
    isUploading.value = false;
  }
}
</script>

<template>
  <div class="card">
    <h2>📤 Upload Document</h2>
    
    <div 
      class="upload-area" 
      :class="{ dragover: isDragging }"
      @click="triggerFileInput"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="upload-icon">📄</div>
      <p><strong>Click to upload</strong> or drag and drop</p>
      <p class="upload-hint">
        Supports PDF documents in Chinese, Japanese, German, French, and English
      </p>
      <input 
        ref="fileInput"
        type="file" 
        @change="handleFileSelect" 
        accept=".pdf,.txt"
        style="display: none"
      >
    </div>

    <div v-if="selectedFile" class="file-selected">
      <label>Selected: <strong>{{ selectedFile.name }}</strong></label>
      <select v-model="selectedLanguage">
        <option v-for="lang in languages" :key="lang" :value="lang">
          {{ languageDisplayNames[lang] }}
        </option>
      </select>
      <button 
        class="btn btn-primary"
        @click="handleUpload"
        :disabled="isUploading"
      >
        {{ isUploading ? 'Uploading...' : 'Upload' }}
      </button>
    </div>

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

.upload-area {
  border: 2px dashed #e5e7eb;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  transition: all 0.3s ease;
  cursor: pointer;
}

.upload-area:hover,
.upload-area.dragover {
  border-color: #2563eb;
  background-color: #eff6ff;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.upload-hint {
  color: #6b7280;
  margin-top: 8px;
}

.file-selected {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.file-selected select {
  padding: 8px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 1rem;
  background: white;
}

.btn {
  display: inline-block;
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: #2563eb;
  color: white;
}

.btn-primary:hover {
  background: #1d4ed8;
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

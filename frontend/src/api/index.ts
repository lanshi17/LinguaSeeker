import type { 
  Document, 
  DocumentListResponse, 
  UploadResponse, 
  AnalysisResult,
  Language 
} from '@/types';

const API_BASE = '/api';

// List all documents
export async function listDocuments(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE}/documents`);
  if (!response.ok) {
    throw new Error(`Failed to load documents: ${response.statusText}`);
  }
  return response.json();
}

// Upload a document
export async function uploadDocument(
  file: File, 
  language: Language
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', language);

  const response = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Upload failed');
  }
  return response.json();
}

// Get a single document
export async function getDocument(id: string): Promise<Document> {
  const response = await fetch(`${API_BASE}/documents/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to get document: ${response.statusText}`);
  }
  return response.json();
}

// Analyze a document
export async function analyzeDocument(id: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE}/documents/${id}/analyze`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Analysis failed');
  }
  return response.json();
}

// Get analysis results for a document
export async function getAnalysisResults(id: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE}/documents/${id}/results`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to load results');
  }
  return response.json();
}

// Health check
export async function healthCheck(): Promise<{ status: string; database: string; version: string }> {
  const response = await fetch(`${API_BASE}/health`);
  return response.json();
}

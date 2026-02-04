/**
 * Document global state management - Zustand
 * Manages current document, selected evidence, view state, etc.
 */
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { DocumentData, TextPosition, EvidenceTypeValue } from '../types';
import { EvidenceType } from '../types';

interface DocumentState {
  currentDocument: DocumentData | null;
  isLoading: boolean;
  error: string | null;
  selectedEvidenceId: string | null;
  highlightedPosition: TextPosition | null;
  pdfCurrentPage: number;
  markdownScrollRatio: number;
  showEvidenceHighlight: boolean;
  enabledEvidenceTypes: EvidenceTypeValue[];
  graphFilter: {
    entityTypes: string[];
    evidenceTypes: string[];
    minConfidence: number;
  };
  taskQueue: Array<{
    id: string;
    type: 'upload' | 'pmid' | 'doi' | 'url';
    status: 'pending' | 'processing' | 'completed' | 'error';
    progress: number;
    error?: string;
  }>;
  setDocument: (doc: DocumentData | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  selectEvidence: (evidenceId: string | null, position?: TextPosition) => void;
  setPdfPage: (page: number) => void;
  setMarkdownScroll: (ratio: number) => void;
  toggleEvidenceHighlight: () => void;
  toggleEvidenceType: (type: EvidenceTypeValue) => void;
  enableAllEvidenceTypes: () => void;
  disableAllEvidenceTypes: () => void;
  updateGraphFilter: (filter: Partial<DocumentState['graphFilter']>) => void;
  addTask: (task: Omit<DocumentState['taskQueue'][0], 'status' | 'progress'>) => void;
  updateTask: (id: string, updates: Partial<DocumentState['taskQueue'][0]>) => void;
  removeTask: (id: string) => void;
  reset: () => void;
}

export const useDocumentStore = create<DocumentState>()(
  devtools(
    persist(
      (set) => ({
        currentDocument: null,
        isLoading: false,
        error: null,
        selectedEvidenceId: null,
        highlightedPosition: null,
        pdfCurrentPage: 1,
        markdownScrollRatio: 0,
        showEvidenceHighlight: true,
        enabledEvidenceTypes: Object.values(EvidenceType),
        graphFilter: {
          entityTypes: [],
          evidenceTypes: [],
          minConfidence: 0.5,
        },
        taskQueue: [],
        setDocument: (doc) => set({ currentDocument: doc }),
        setLoading: (loading) => set({ isLoading: loading }),
        setError: (error) => set({ error }),
        selectEvidence: (evidenceId, position) => set({
          selectedEvidenceId: evidenceId,
          highlightedPosition: position || null,
        }),
        setPdfPage: (page) => set({ pdfCurrentPage: page }),
        setMarkdownScroll: (ratio) => set({ markdownScrollRatio: ratio }),
        toggleEvidenceHighlight: () => set((state) => ({ 
          showEvidenceHighlight: !state.showEvidenceHighlight 
        })),
        toggleEvidenceType: (type) => set((state) => ({
          enabledEvidenceTypes: state.enabledEvidenceTypes.includes(type)
            ? state.enabledEvidenceTypes.filter((t) => t !== type)
            : [...state.enabledEvidenceTypes, type],
        })),
        enableAllEvidenceTypes: () => set({ enabledEvidenceTypes: Object.values(EvidenceType) }),
        disableAllEvidenceTypes: () => set({ enabledEvidenceTypes: [] }),
        updateGraphFilter: (filter) => set((state) => ({
          graphFilter: { ...state.graphFilter, ...filter },
        })),
        addTask: (task) => set((state) => ({
          taskQueue: [...state.taskQueue, { ...task, status: 'pending', progress: 0 }],
        })),
        updateTask: (id, updates) => set((state) => ({
          taskQueue: state.taskQueue.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        })),
        removeTask: (id) => set((state) => ({
          taskQueue: state.taskQueue.filter((t) => t.id !== id),
        })),
        reset: () => set({
          currentDocument: null,
          selectedEvidenceId: null,
          highlightedPosition: null,
          pdfCurrentPage: 1,
          markdownScrollRatio: 0,
          error: null,
        }),
      }),
      {
        name: 'document-storage',
        partialize: (state) => ({
          graphFilter: state.graphFilter,
        }),
      }
    )
  )
);

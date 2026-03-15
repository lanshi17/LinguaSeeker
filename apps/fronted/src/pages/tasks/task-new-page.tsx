import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { interactionRespond, interactionStart, uploadTaskRequest } from '../../services/api';
import { ApiError } from '../../services/http';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';
import { validateUploadFiles } from '../../utils/validation';

import type { TaskFormStructured } from '../../types/api';

function buildUserInput(form: TaskFormStructured) {
  return `Goal: ${form.goal}\nDisease: ${form.disease}\nCountry: ${form.country}\nLanguage: ${form.language}`;
}

export const TaskNewPage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToastStore();
  const { taskForm, interactionSessionId, interactionRound, setTaskForm, setInteraction } = useTaskFlowStore();

  const [draft, setDraft] = useState<TaskFormStructured>(() =>
    taskForm ?? {
      goal: '',
      disease: '',
      country: '不限',
      language: 'auto'
    }
  );

  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<File[]>([]);

  const ready = Boolean(taskForm);
  const canClarify = interactionRound < 2;

  const userInput = useMemo(() => buildUserInput(draft), [draft]);

  const start = async () => {
    if (!draft.goal.trim() || !draft.disease.trim()) {
      toast.pushToast({ level: 'warning', title: 'Missing fields', message: 'Goal and disease are required', ttlMs: 5000 });
      return;
    }

    setBusy(true);
    try {
      const res = await interactionStart({ user_input: userInput });
      setInteraction(res.session_id, res.round);
      setQuestion(res.question);
      if (res.task_form) {
        setTaskForm(res.task_form);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to start interaction';
      toast.pushToast({ level: 'error', title: 'Interaction failed', message: msg, ttlMs: 8000 });
    } finally {
      setBusy(false);
    }
  };

  const respond = async () => {
    if (!interactionSessionId) return;
    if (!answer.trim()) {
      toast.pushToast({ level: 'warning', title: 'Empty response', message: 'Please answer the question', ttlMs: 5000 });
      return;
    }

    setBusy(true);
    try {
      const res = await interactionRespond({ session_id: interactionSessionId, user_response: answer });
      setInteraction(interactionSessionId, res.round);
      setQuestion(res.question);
      setAnswer('');
      if (res.task_form) {
        setTaskForm(res.task_form);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to respond';
      toast.pushToast({ level: 'error', title: 'Interaction failed', message: msg, ttlMs: 8000 });
    } finally {
      setBusy(false);
    }
  };

  const submitUpload = async () => {
    if (!taskForm) return;
    const validation = validateUploadFiles(files);
    if (!validation.ok) {
      toast.pushToast({
        level: 'error',
        title: 'Upload validation failed',
        message: validation.issues.map((i) => `${i.code}: ${i.message}`).join(' | '),
        ttlMs: 10000
      });
      return;
    }

    setBusy(true);
    try {
      const res = await uploadTaskRequest(taskForm, files);
      navigate(`/requests/${encodeURIComponent(res.request_id)}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Upload failed';
      toast.pushToast({ level: 'error', title: 'Upload failed', message: msg, ttlMs: 9000 });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="panel">
        <div className="panel-header">
          <div>
            <div style={{ fontWeight: 900 }}>Create Task</div>
            <div className="muted" style={{ fontSize: 12 }}>
              Clarification rounds: {interactionRound}/2
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            OpenAPI interaction expects a free-text prompt; we format the structured form into a prompt.
          </div>
        </div>
        <div className="panel-body">
          <div className="row">
            <label className="col">
              <div className="muted">Goal</div>
              <input
                value={draft.goal}
                onChange={(e) => setDraft((s) => ({ ...s, goal: e.target.value }))}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
                placeholder="e.g., Evaluate PS3 evidence for variant ..."
              />
            </label>
            <label className="col">
              <div className="muted">Disease</div>
              <input
                value={draft.disease}
                onChange={(e) => setDraft((s) => ({ ...s, disease: e.target.value }))}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
                placeholder="e.g., cystic fibrosis"
              />
            </label>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <label className="col">
              <div className="muted">Country</div>
              <input
                value={draft.country}
                onChange={(e) => setDraft((s) => ({ ...s, country: e.target.value }))}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
              />
            </label>
            <label className="col">
              <div className="muted">Language</div>
              <input
                value={draft.language}
                onChange={(e) => setDraft((s) => ({ ...s, language: e.target.value }))}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
              />
            </label>
          </div>

          <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={start}
              disabled={busy || !canClarify}
              style={{
                padding: '10px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'rgba(124,92,255,0.18)',
                color: 'var(--text)',
                cursor: busy ? 'not-allowed' : 'pointer'
              }}
            >
              Start clarification
            </button>
            {!canClarify ? (
              <div className="muted" style={{ alignSelf: 'center' }}>
                Max clarification rounds reached.
              </div>
            ) : null}
          </div>

          {question ? (
            <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              <div style={{ fontWeight: 800 }}>Question</div>
              <div className="muted" style={{ marginTop: 6 }}>
                {question}
              </div>
              <div style={{ marginTop: 10 }}>
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={4}
                  style={{
                    width: '100%',
                    padding: 10,
                    borderRadius: 12,
                    border: '1px solid var(--border)',
                    background: 'transparent',
                    color: 'var(--text)'
                  }}
                  placeholder="Your answer"
                />
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  onClick={respond}
                  disabled={busy || !canClarify}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 12,
                    border: '1px solid var(--border)',
                    background: 'rgba(255,255,255,0.06)',
                    color: 'var(--text)',
                    cursor: busy ? 'not-allowed' : 'pointer'
                  }}
                >
                  Send answer
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div style={{ fontWeight: 900 }}>Next</div>
          <div className="muted" style={{ fontSize: 12 }}>
            {ready ? 'Task form ready' : 'Complete clarification to continue'}
          </div>
        </div>
        <div className="panel-body">
          {!ready ? (
            <div className="muted">Waiting for structured task form from backend...</div>
          ) : (
            <div className="row">
              <div className="col" style={{ minWidth: 320 }}>
                <div style={{ fontWeight: 800 }}>Upload PDFs/DOCX</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  Max 10 files, 10MB each, 50MB total.
                </div>
                <div style={{ marginTop: 10 }}>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx"
                    onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                  />
                </div>
                {files.length > 0 ? (
                  <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                    Selected: {files.map((f) => f.name).join(', ')}
                  </div>
                ) : null}
                <div style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    onClick={submitUpload}
                    disabled={busy || files.length === 0}
                    style={{
                      padding: '10px 14px',
                      borderRadius: 12,
                      border: '1px solid var(--border)',
                      background: 'rgba(82,196,26,0.16)',
                      color: 'var(--text)',
                      cursor: busy ? 'not-allowed' : 'pointer'
                    }}
                  >
                    Submit upload
                  </button>
                </div>
              </div>

              <div className="col" style={{ minWidth: 320 }}>
                <div style={{ fontWeight: 800 }}>PubMed candidates</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  Search literature, select 1–10 PMIDs.
                </div>
                <div style={{ marginTop: 10 }}>
                  <Link to="/tasks/pubmed/candidates">Go to candidates</Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

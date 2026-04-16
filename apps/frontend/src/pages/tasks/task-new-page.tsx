import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { confirmTaskForm, stringifyTaskForm, uploadTaskRequest, webCrawlSubmit } from '../../services/api';
import { ApiError } from '../../services/http';
import { AgentClarificationChat } from '../../components/chat/agent-clarification-chat';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';
import { validateUploadFiles } from '../../utils/validation';

import type { TaskFormStructured } from '../../types/api';

type ExpertFeedbackItem = {
  tone: 'info' | 'warning' | 'success';
  text: string;
  action?: 'confirm_now' | 'go_candidates';
};

function buildUserInput(form: TaskFormStructured) {
  return `Goal: ${form.goal}\nDisease: ${form.disease}\nCountry: ${form.country}\nLanguage: ${form.language}`;
}

function buildExpertFeedback(params: {
  taskForm: TaskFormStructured | null;
  interactionRound: number;
  confirmedRequestId: string | null;
  filesCount: number;
}) {
  const items: ExpertFeedbackItem[] = [];
  const { taskForm, interactionRound, confirmedRequestId, filesCount } = params;

  if (!taskForm) {
    items.push({
      tone: 'warning',
      text: 'Continue clarification until a structured task form is returned by backend.',
    });
  }

  if (taskForm && !confirmedRequestId) {
    items.push({
      tone: 'info',
      text: 'Confirm the task form to lock the request id before branching.',
      action: 'confirm_now',
    });
  }

  if (confirmedRequestId && filesCount === 0) {
    items.push({
      tone: 'info',
      text: 'Request is confirmed. You can upload files or continue to PubMed candidates.',
      action: 'go_candidates',
    });
  }

  if (confirmedRequestId && filesCount > 0) {
    items.push({
      tone: 'success',
      text: `Files selected (${filesCount}). Submit upload when ready.`,
    });
  }

  if (interactionRound >= 2 && !taskForm) {
    items.push({
      tone: 'warning',
      text: 'Clarification rounds reached limit; restart clarification if the task form is still missing.',
    });
  }

  return items;
}

function parseWebUrls(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export const TaskNewPage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToastStore();
  const { taskForm, interactionRound, taskFormPayload, confirmedRequestId, setConfirmedRequestId } = useTaskFlowStore();

  const [draft, setDraft] = useState<TaskFormStructured>(() =>
    taskForm ?? {
      goal: '',
      disease: '',
      country: '不限',
      language: 'auto'
    }
  );

  useEffect(() => {
    if (taskForm) {
      setDraft(taskForm);
    }
  }, [taskForm]);

  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [webUrlsText, setWebUrlsText] = useState('');
  const [forceRefresh, setForceRefresh] = useState(false);

  const ready = Boolean(taskForm);
  const expertFeedback = useMemo(
    () => buildExpertFeedback({ taskForm, interactionRound, confirmedRequestId, filesCount: files.length }),
    [confirmedRequestId, files.length, interactionRound, taskForm]
  );

  const userInput = useMemo(() => buildUserInput(draft), [draft]);

  const handleDraftChange = (updates: Partial<TaskFormStructured>) => {
    setDraft((s) => ({ ...s, ...updates }));
    if (confirmedRequestId) {
      setConfirmedRequestId(null);
    }
  };

  const submitUpload = async () => {
    if (!confirmedRequestId && !taskForm) return;
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
      const res = await uploadTaskRequest(confirmedRequestId || taskForm!, files);
      navigate(`/requests/${encodeURIComponent(res.request_id)}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Upload failed';
      toast.pushToast({ level: 'error', title: 'Upload failed', message: msg, ttlMs: 9000 });
    } finally {
      setBusy(false);
    }
  };

  const submitWebCrawl = async () => {
    if (!confirmedRequestId) return;

    const urls = parseWebUrls(webUrlsText);
    if (urls.length === 0) {
      toast.pushToast({
        level: 'error',
        title: 'Web crawl validation failed',
        message: 'Please enter at least one URL.',
        ttlMs: 8000,
      });
      return;
    }

    try {
      urls.forEach((value) => {
        new URL(value);
      });
    } catch {
      toast.pushToast({
        level: 'error',
        title: 'Web crawl validation failed',
        message: 'Please enter valid absolute URLs, one per line.',
        ttlMs: 8000,
      });
      return;
    }

    setBusy(true);
    try {
      const res = await webCrawlSubmit({
        task_form: stringifyTaskForm(draft),
        urls,
        source: 'web',
        force_refresh: forceRefresh,
      });
      navigate(`/requests/${encodeURIComponent(res.request_id)}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Web crawl request failed';
      toast.pushToast({ level: 'error', title: 'Web crawl failed', message: msg, ttlMs: 9000 });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async () => {
    setBusy(true);
    try {
      const payload = { ...(taskFormPayload || {}), ...draft };
      const res = await confirmTaskForm({ task_form_payload: payload });
      if (res.confirmed) {
        setConfirmedRequestId(res.request_id);
        toast.pushToast({ level: 'success', title: 'Task Confirmed', message: 'Ready for upload or candidates', ttlMs: 3000 });
      } else {
        toast.pushToast({ level: 'warning', title: 'Not Confirmed', message: 'Could not confirm task', ttlMs: 5000 });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Confirmation failed';
      toast.pushToast({ level: 'error', title: 'Confirm failed', message: msg, ttlMs: 8000 });
    } finally {
      setBusy(false);
    }
  };

  const handleFeedbackAction = (action: ExpertFeedbackItem['action']) => {
    if (!action) return;
    if (action === 'confirm_now') {
      if (!busy) {
        void handleConfirm();
      }
      return;
    }
    if (action === 'go_candidates' && confirmedRequestId && !busy) {
      navigate('/tasks/pubmed/candidates');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="panel">
          <div className="panel-header">
            <div>
              <h2 style={{ fontWeight: 900, margin: 0, fontSize: 16 }}>Clarification</h2>
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
                onChange={(e) => handleDraftChange({ goal: e.target.value })}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
                placeholder="e.g., Evaluate PS3 evidence for variant ..."
              />
            </label>
            <label className="col">
              <div className="muted">Disease</div>
              <input
                value={draft.disease}
                onChange={(e) => handleDraftChange({ disease: e.target.value })}
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
                onChange={(e) => handleDraftChange({ country: e.target.value })}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
              />
            </label>
            <label className="col">
              <div className="muted">Language</div>
              <input
                value={draft.language}
                onChange={(e) => handleDraftChange({ language: e.target.value })}
                style={{ width: '100%', padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}
              />
            </label>
          </div>

          <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <AgentClarificationChat draft={draft} userInput={userInput} busy={busy} setBusy={setBusy} />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 style={{ fontWeight: 900, margin: 0, fontSize: 16 }}>Task-sheet confirmation</h2>
            <div className="muted" style={{ fontSize: 12 }}>
              {ready ? 'Task form ready' : 'Complete clarification to continue'}
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12 }}>Confirm, then choose a branch.</div>
        </div>
        <div className="panel-body">
          {!ready ? (
            <div className="muted">Waiting for structured task form from backend...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {confirmedRequestId ? (
                <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(82,196,26,0.1)', color: '#237804' }}>
                  <span style={{ fontWeight: 'bold' }}>✓ Confirmed!</span> Request ID: {confirmedRequestId}
                </div>
              ) : (
                <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(250,173,20,0.1)', color: '#ad6800' }}>
                  <div style={{ marginBottom: '8px' }}>Please review and confirm the task form before continuing.</div>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    disabled={busy}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: '1px solid var(--border)',
                      background: 'var(--bg-elevated)',
                      cursor: busy ? 'not-allowed' : 'pointer'
                    }}
                  >
                    Confirm Task Form
                  </button>
                </div>
              )}

              <div
                style={{
                  padding: 12,
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  background: 'var(--bg-elevated)',
                }}
              >
                <h3 style={{ fontWeight: 800, margin: 0, fontSize: 14 }}>Expert feedback</h3>
                <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                  Plan-aligned review hints before upload/candidate branching.
                </div>
                <ul style={{ margin: '10px 0 0', paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {expertFeedback.map((item, index) => (
                    <li
                      key={`${item.tone}-${index}`}
                      style={{
                        color:
                          item.tone === 'warning'
                            ? '#ad6800'
                            : item.tone === 'success'
                              ? '#237804'
                              : 'var(--text-muted)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                        <span>{item.text}</span>
                        {item.action ? (
                          <button
                            type="button"
                            onClick={() => handleFeedbackAction(item.action)}
                            disabled={busy}
                            style={{
                              padding: '6px 10px',
                              borderRadius: 8,
                              border: '1px solid var(--border)',
                              background: 'var(--bg-elevated)',
                              cursor: busy ? 'not-allowed' : 'pointer',
                            }}
                          >
                            {item.action === 'confirm_now' ? 'Confirm now' : 'Open candidates shortcut'}
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="row">
                <div className="col" style={{ minWidth: 320 }}>
                  <h3 style={{ fontWeight: 800, margin: 0 }}>Branch actions</h3>
                  <div className="muted" style={{ marginTop: 6 }}>
                    Choose whether to upload documents or continue to candidate retrieval.
                  </div>
                  <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <div>
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
                          disabled={busy || files.length === 0 || !confirmedRequestId}
                          style={{
                            padding: '10px 14px',
                            borderRadius: 12,
                            border: '1px solid var(--border)',
                            background: 'rgba(82,196,26,0.16)',
                            color: 'var(--text)',
                            cursor: (busy || !confirmedRequestId) ? 'not-allowed' : 'pointer',
                            opacity: (!confirmedRequestId || files.length === 0) ? 0.5 : 1
                          }}
                        >
                          Submit upload
                        </button>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontWeight: 800 }}>PubMed candidates</div>
                      <div className="muted" style={{ marginTop: 6 }}>
                        Search literature, select 1–10 PMIDs.
                      </div>
                      <div style={{ marginTop: 10 }}>
                        {confirmedRequestId ? (
                          <button
                            type="button"
                            onClick={() => navigate('/tasks/pubmed/candidates')}
                            disabled={busy}
                            style={{
                              padding: '10px 14px',
                              borderRadius: 12,
                              border: '1px solid var(--border)',
                              background: 'rgba(24,144,255,0.1)',
                              color: 'var(--text)',
                              cursor: busy ? 'not-allowed' : 'pointer',
                              opacity: busy ? 0.5 : 1
                            }}
                          >
                            Go to candidates
                          </button>
                        ) : (
                          <span className="muted" style={{ fontSize: 12 }}>Confirmation required</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontWeight: 800 }}>Web crawl</div>
                      <div className="muted" style={{ marginTop: 6 }}>
                        Submit one or more URLs for crawl-based intake.
                      </div>
                      <div style={{ marginTop: 10 }}>
                        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          <span className="muted" style={{ fontSize: 12 }}>Web URLs</span>
                          <textarea
                            value={webUrlsText}
                            onChange={(e) => setWebUrlsText(e.target.value)}
                            placeholder="https://example.com/a&#10;https://example.com/b"
                            rows={4}
                            style={{
                              width: '100%',
                              padding: 10,
                              borderRadius: 12,
                              border: '1px solid var(--border)',
                              background: 'var(--bg-elevated)',
                              color: 'var(--text)',
                              resize: 'vertical',
                            }}
                          />
                        </label>
                      </div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12 }}>
                        <input
                          type="checkbox"
                          checked={forceRefresh}
                          onChange={(e) => setForceRefresh(e.target.checked)}
                          disabled={busy || !confirmedRequestId}
                        />
                        Force refresh existing crawl targets
                      </label>
                      <div style={{ marginTop: 10 }}>
                        <button
                          type="button"
                          onClick={submitWebCrawl}
                          disabled={busy || !confirmedRequestId}
                          style={{
                            padding: '10px 14px',
                            borderRadius: 12,
                            border: '1px solid var(--border)',
                            background: 'rgba(250,173,20,0.12)',
                            color: 'var(--text)',
                            cursor: (busy || !confirmedRequestId) ? 'not-allowed' : 'pointer',
                            opacity: confirmedRequestId ? (busy ? 0.5 : 1) : 0.5,
                          }}
                        >
                          Submit web crawl
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

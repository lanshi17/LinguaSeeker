import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { literatureSelectionSubmit, stringifyTaskForm } from '../../services/api';
import { ApiError } from '../../services/http';
import { useAppStore } from '../../store/appStore';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';

const MAX_SELECT = 10;

export const LiteratureCandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const pushToast = useToastStore((s) => s.pushToast);
  const { taskForm, confirmedRequestId } = useTaskFlowStore();
  const { candidates, ui, fetchCandidates, toggleCandidateSelection, clearCandidateSelection } = useAppStore();

  const [loading, setLoading] = useState(false);

  const selectionCount = ui.selectedCandidateIds.length;
  const selectionValid = selectionCount >= 1 && selectionCount <= MAX_SELECT;

  const selectedCandidates = useMemo(
    () => candidates.filter((candidate) => ui.selectedCandidateIds.includes(candidate.candidate_id)),
    [candidates, ui.selectedCandidateIds]
  );

  useEffect(() => {
    if (!taskForm && !confirmedRequestId) return;
    let cancelled = false;
    setLoading(true);

    const payload = {
      request_id: confirmedRequestId ?? undefined,
      task_form: taskForm ? stringifyTaskForm(taskForm) : undefined,
      target: taskForm?.goal ?? '',
      disease: taskForm?.disease ?? '',
      country: taskForm?.country,
      language: taskForm?.language,
      source: 'literature',
      candidate_limit: 15,
    };

    fetchCandidates(payload)
      .catch((err) => {
        const msg = err instanceof ApiError ? err.detail ?? err.message : 'Candidate search failed';
        pushToast({ level: 'error', title: 'Search failed', message: msg, ttlMs: 9000 });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [taskForm, confirmedRequestId, fetchCandidates, pushToast]);

  const toggle = (candidateId: string) => {
    if (ui.selectedCandidateIds.includes(candidateId)) {
      toggleCandidateSelection(candidateId);
      return;
    }

    if (ui.selectedCandidateIds.length >= MAX_SELECT) {
      pushToast({ level: 'warning', title: 'Selection limit', message: `Max ${MAX_SELECT} papers`, ttlMs: 5000 });
      return;
    }

    toggleCandidateSelection(candidateId);
  };

  const submit = async () => {
    if (!taskForm && !confirmedRequestId) return;
    if (!selectionValid) {
      pushToast({ level: 'warning', title: 'Invalid selection', message: 'Select 1–10 papers', ttlMs: 6000 });
      return;
    }
    setLoading(true);
    try {
      const res = await literatureSelectionSubmit({
        request_id: confirmedRequestId ?? undefined,
        task_form: taskForm ? stringifyTaskForm(taskForm) : undefined,
        selected_candidates: selectedCandidates,
        source: 'literature'
      });
      navigate(`/requests/${encodeURIComponent(res.request_id ?? confirmedRequestId ?? 'unknown')}`);
      clearCandidateSelection();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Submit failed';
      pushToast({ level: 'error', title: 'Submit failed', message: msg, ttlMs: 9000 });
    } finally {
      setLoading(false);
    }
  };

  if (!taskForm && !confirmedRequestId) {
    return (
      <div className="panel">
        <div className="panel-header">
          <div style={{ fontWeight: 900 }}>Online literature candidates</div>
        </div>
        <div className="panel-body">
          <div className="muted">Confirmation state or task form not found. Please create a task first.</div>
          <div style={{ marginTop: 10 }}>
            <Link to="/tasks/new">Go to task creation</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div style={{ fontWeight: 900 }}>Online literature candidates</div>
          <div className="muted" style={{ fontSize: 12 }}>
            Select 1–10 papers. Returned: {candidates.length}.
          </div>
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={loading || !selectionValid}
          style={{
            padding: '10px 14px',
            borderRadius: 12,
            border: '1px solid var(--border)',
            background: selectionValid ? 'rgba(124,92,255,0.18)' : 'rgba(255,255,255,0.06)',
            color: 'var(--text)',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          Submit selection ({selectionCount})
        </button>
      </div>
      <div className="panel-body">
        {loading ? <div className="muted">Loading...</div> : null}
        {candidates.length === 0 && !loading ? <div className="muted">No candidates</div> : null}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {candidates.map((candidate) => {
            const checked = ui.selectedCandidateIds.includes(candidate.candidate_id);
            const meta = [candidate.provider, candidate.route, candidate.language].filter(Boolean).join(' · ');
            return (
              <label
                key={candidate.candidate_id}
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 12,
                  display: 'flex',
                  gap: 12,
                  alignItems: 'flex-start',
                  background: checked ? 'rgba(124,92,255,0.10)' : 'rgba(255,255,255,0.03)'
                }}
              >
                <input type="checkbox" checked={checked} onChange={() => toggle(candidate.candidate_id)} />
                <div>
                  <div style={{ fontWeight: 800 }}>{candidate.title}</div>
                  <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                    {meta || 'Unknown source'}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
};

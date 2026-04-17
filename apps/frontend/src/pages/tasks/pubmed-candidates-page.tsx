import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { pubmedSelectionSubmit, stringifyTaskForm } from '../../services/api';
import { ApiError } from '../../services/http';
import { useAppStore } from '../../store/appStore';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';

const MAX_SELECT = 10;

export const PubmedCandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const pushToast = useToastStore((s) => s.pushToast);
  const { taskForm, confirmedRequestId } = useTaskFlowStore();
  const { candidates, ui, fetchCandidates, togglePmidSelection, clearPmidSelection } = useAppStore();

  const [loading, setLoading] = useState(false);

  const selectionCount = ui.selectedPmids.length;
  const selectionValid = selectionCount >= 1 && selectionCount <= MAX_SELECT;

  const selectedList = useMemo(() => ui.selectedPmids, [ui.selectedPmids]);

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
      source: 'pubmed',
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

  const toggle = (pmid: string) => {
    if (ui.selectedPmids.includes(pmid)) {
      togglePmidSelection(pmid);
      return;
    }

    if (ui.selectedPmids.length >= MAX_SELECT) {
      pushToast({ level: 'warning', title: 'Selection limit', message: `Max ${MAX_SELECT} papers`, ttlMs: 5000 });
      return;
    }

    togglePmidSelection(pmid);
  };

  const submit = async () => {
    if (!taskForm && !confirmedRequestId) return;
    if (!selectionValid) {
      pushToast({ level: 'warning', title: 'Invalid selection', message: 'Select 1–10 PMIDs', ttlMs: 6000 });
      return;
    }
    setLoading(true);
    try {
      const res = await pubmedSelectionSubmit({
        request_id: confirmedRequestId ?? undefined,
        task_form: taskForm ? stringifyTaskForm(taskForm) : undefined,
        selected_pmids: selectedList,
        target: taskForm?.goal ?? '',
        disease: taskForm?.disease ?? '',
        country: taskForm?.country,
        language: taskForm?.language,
        source: 'pubmed'
      });
      navigate(`/requests/${encodeURIComponent(res.request_id ?? confirmedRequestId ?? 'unknown')}`);
      clearPmidSelection();
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
          <div style={{ fontWeight: 900 }}>PubMed candidates</div>
        </div>
        <div className="panel-body">
          <div className="muted">Confirmation state or task form not found. Please create a task first.</div>
          <div style={{ marginTop: 10 }}>
            <Link to="/tasks/agent-create">Go to task creation</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <div style={{ fontWeight: 900 }}>PubMed candidates</div>
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
          {candidates.map((c) => {
            const checked = ui.selectedPmids.includes(c.pmid);
            return (
              <label
                key={c.pmid}
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
                <input type="checkbox" checked={checked} onChange={() => toggle(c.pmid)} />
                <div>
                  <div style={{ fontWeight: 800 }}>{c.title}</div>
                  <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                    PMID: {c.pmid} · {c.journal} · {c.pub_date}
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

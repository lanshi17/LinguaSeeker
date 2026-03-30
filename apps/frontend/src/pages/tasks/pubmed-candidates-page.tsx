import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { pubmedCandidateSearch, pubmedSelectionSubmit, stringifyTaskForm } from '../../services/api';
import { ApiError } from '../../services/http';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';

import type { PubMedCandidateItem } from '../../types/api';

const MAX_SELECT = 10;

export const PubmedCandidatesPage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToastStore();
  const { taskForm, confirmedRequestId } = useTaskFlowStore();

  const [candidates, setCandidates] = useState<PubMedCandidateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const selectionCount = selected.size;
  const selectionValid = selectionCount >= 1 && selectionCount <= MAX_SELECT;

  const selectedList = useMemo(() => Array.from(selected), [selected]);

  useEffect(() => {
    if (!taskForm && !confirmedRequestId) return;
    let cancelled = false;
    setLoading(true);
    pubmedCandidateSearch({
      request_id: confirmedRequestId ?? undefined,
      task_form: taskForm ? stringifyTaskForm(taskForm) : undefined,
      target: taskForm?.goal ?? '',
      disease: taskForm?.disease ?? '',
      country: taskForm?.country,
      language: taskForm?.language,
      source: 'pubmed',
      candidate_limit: 15
    })
      .then((res) => {
        if (!cancelled) setCandidates(res.candidates ?? []);
      })
      .catch((err) => {
        const msg = err instanceof ApiError ? err.detail ?? err.message : 'Candidate search failed';
        toast.pushToast({ level: 'error', title: 'Search failed', message: msg, ttlMs: 9000 });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [taskForm, confirmedRequestId, toast]);

  const toggle = (pmid: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(pmid)) {
        next.delete(pmid);
      } else {
        if (next.size >= MAX_SELECT) {
          toast.pushToast({ level: 'warning', title: 'Selection limit', message: `Max ${MAX_SELECT} papers`, ttlMs: 5000 });
          return prev;
        }
        next.add(pmid);
      }
      return next;
    });
  };

  const submit = async () => {
    if (!taskForm && !confirmedRequestId) return;
    if (!selectionValid) {
      toast.pushToast({ level: 'warning', title: 'Invalid selection', message: 'Select 1–10 PMIDs', ttlMs: 6000 });
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
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Submit failed';
      toast.pushToast({ level: 'error', title: 'Submit failed', message: msg, ttlMs: 9000 });
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
            const checked = selected.has(c.pmid);
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

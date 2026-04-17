import type { WorkflowTimelineStep, WorkflowTimelineStatus } from '../../types/stream';

type WorkflowTimelineProps = {
  steps: WorkflowTimelineStep[];
  emptyMessage?: string;
  title?: string;
};

function pillColor(status: WorkflowTimelineStatus) {
  if (status === 'completed') return 'rgba(82,196,26,0.22)';
  if (status === 'error') return 'rgba(255,77,79,0.22)';
  if (status === 'running') return 'rgba(124,92,255,0.22)';
  return 'rgba(255,255,255,0.08)';
}

export function WorkflowTimeline({ steps, emptyMessage = 'No workflow data yet', title }: WorkflowTimelineProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {title ? <div style={{ fontWeight: 900 }}>{title}</div> : null}
      {steps.length === 0 ? (
        <div className="muted">{emptyMessage}</div>
      ) : (
        steps.map((step) => (
          <div
            key={step.id}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 800 }}>{step.label}</div>
              {step.description ? (
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  {step.description}
                </div>
              ) : null}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {typeof step.progress === 'number' ? (
                <div className="muted" style={{ fontSize: 12 }}>
                  {step.progress}%
                </div>
              ) : null}
              <div
                style={{
                  padding: '6px 10px',
                  borderRadius: 999,
                  border: '1px solid var(--border)',
                  background: pillColor(step.status),
                  fontSize: 12,
                }}
              >
                {step.status}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

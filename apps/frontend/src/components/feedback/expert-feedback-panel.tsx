type ExpertFeedbackAction = 'confirm_now' | 'go_candidates';

type ExpertFeedbackItem = {
  tone: 'info' | 'warning' | 'success';
  text: string;
  action?: ExpertFeedbackAction;
};

type ExpertFeedbackPanelProps = {
  busy?: boolean;
  items: ExpertFeedbackItem[];
  onAction: (action: ExpertFeedbackAction) => void;
};

const toneColorMap: Record<ExpertFeedbackItem['tone'], string> = {
  info: 'var(--text-muted)',
  warning: '#ad6800',
  success: '#237804',
};

const actionLabelMap: Record<ExpertFeedbackAction, string> = {
  confirm_now: 'Confirm now',
  go_candidates: 'Open candidates shortcut',
};

export const ExpertFeedbackPanel: React.FC<ExpertFeedbackPanelProps> = ({ busy = false, items, onAction }) => {
  return (
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
        {items.map((item, index) => (
          <li key={`${item.tone}-${index}`} style={{ color: toneColorMap[item.tone] }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span>{item.text}</span>
              {item.action ? (
                <button
                  type="button"
                  onClick={() => onAction(item.action!)}
                  disabled={busy}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-elevated)',
                    cursor: busy ? 'not-allowed' : 'pointer',
                  }}
                >
                  {actionLabelMap[item.action]}
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export type { ExpertFeedbackAction, ExpertFeedbackItem };

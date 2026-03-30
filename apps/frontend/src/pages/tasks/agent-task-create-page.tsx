import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { useWorkflowStore } from '../../store/useWorkflowStore';

export function AgentTaskCreatePage() {
  const navigate = useNavigate();
  const requestTimeline = useWorkflowStore((s) => s.requestTimeline);
  const taskTimeline = useWorkflowStore((s) => s.taskTimeline);
  const requestConnection = useWorkflowStore((s) => s.requestConnection);
  const reset = useWorkflowStore((s) => s.reset);

  const isConnected = requestConnection.connected;
  const hasStream = isConnected || requestTimeline.some((t) => t.status !== 'pending');

  useEffect(() => () => { reset(); }, [reset]);

  return (
    <div className="agent-task-create-page" data-testid="agent-task-create-page">
      <h1>Agent-driven task creation</h1>

      <section aria-labelledby="conversation-heading">
        <h2 id="conversation-heading">Conversation</h2>
        <p className="section-description">
          Use the guided task form to provide variant information and upload
          or search for literature.
        </p>
        <button
          type="button"
          onClick={() => { navigate('/tasks/new'); }}
        >
          Open task form flow
        </button>
      </section>

      <section aria-labelledby="workflow-heading">
        <h2 id="workflow-heading">Workflow status</h2>
        {!hasStream ? (
          <p>No workflow stream connected yet</p>
        ) : (
          <>
            {requestTimeline.length > 0 && (
              <div className="request-timeline">
                <h3>Request</h3>
                <ol>
                  {requestTimeline.map((step) => (
                    <li key={step.id} data-status={step.status}>
                      <span className="step-label">{step.label}</span>
                      {step.description && (
                        <span className="step-description">{step.description}</span>
                      )}
                      {step.progress !== undefined && (
                        <span className="step-progress">{step.progress}%</span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {taskTimeline.length > 0 && (
              <div className="task-timeline">
                <h3>Task</h3>
                <ol>
                  {taskTimeline.map((step) => (
                    <li key={step.id} data-status={step.status}>
                      <span className="step-label">{step.label}</span>
                      {step.description && (
                        <span className="step-description">{step.description}</span>
                      )}
                      {step.progress !== undefined && (
                        <span className="step-progress">{step.progress}%</span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

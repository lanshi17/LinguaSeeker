import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { WorkflowTimeline } from '../../components/workflow/workflow-timeline';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

function formatConnectionState(connected: boolean) {
  return connected ? 'connected' : 'disconnected';
}

export function AgentTaskCreatePage() {
  const navigate = useNavigate();
  const entryMode = useTaskFlowStore((s) => s.entryMode);
  const requestTimeline = useWorkflowStore((s) => s.requestTimeline);
  const taskTimeline = useWorkflowStore((s) => s.taskTimeline);
  const requestConnection = useWorkflowStore((s) => s.requestConnection);
  const taskConnection = useWorkflowStore((s) => s.taskConnection);
  const reset = useWorkflowStore((s) => s.reset);

  const hasStream =
    requestConnection.connected
    || taskConnection.connected
    || requestTimeline.some((t) => t.status !== 'pending')
    || taskTimeline.some((t) => t.status !== 'pending');

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
        <p>Entry mode: {entryMode ?? 'not set'}</p>
        <p>Request connection: {formatConnectionState(requestConnection.connected)}</p>
        <p>Task connection: {formatConnectionState(taskConnection.connected)}</p>
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <WorkflowTimeline steps={requestTimeline} title="Request" />
            <WorkflowTimeline steps={taskTimeline} title="Task" />
          </div>
        )}
      </section>
    </div>
  );
}

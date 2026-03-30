import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { InteractionRespondResponse } from '../../types/api';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('../../services/api', () => ({
  interactionStart: vi.fn(),
  interactionRespond: vi.fn(),
}));

describe('AgentClarificationChat transcript persistence', () => {
  beforeEach(async () => {
    vi.resetModules();
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });

    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    useTaskFlowStore.setState({
      taskForm: null,
      interactionSessionId: null,
      interactionRound: 0,
      entryMode: null,
      confirmedRequestId: null,
      taskFormPayload: null,
      interactionMessages: [],
    } as never);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('does not show transcript-missing warning when store has messages for an active session', async () => {
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    useTaskFlowStore.setState({
      interactionSessionId: 'sess-1',
      interactionRound: 1,
      taskForm: null,
      entryMode: 'documents',
      interactionMessages: [
        { id: 'm1', role: 'assistant', text: 'Question?', createdAtMs: Date.now() },
        { id: 'm2', role: 'user', text: 'Answer', createdAtMs: Date.now() },
      ],
    } as never);

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    expect(screen.queryByText(/聊天记录已丢失/i)).not.toBeInTheDocument();
    expect(screen.getByText('Question?')).toBeInTheDocument();
    expect(screen.getByText('Answer')).toBeInTheDocument();
  });

  it('uses clarification_question when question is absent on start response', async () => {
    const { interactionStart } = await import('../../services/api');
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    vi.mocked(interactionStart).mockResolvedValue({
      session_id: 'sess-2',
      ready: false,
      task_form: null,
      question: null,
      clarification_question: '请补充证据来源',
      needs_clarification: true,
      round: 1,
    });

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '解析文档' }));
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));

    expect(await screen.findByText('请补充证据来源')).toBeInTheDocument();
    expect(useTaskFlowStore.getState().interactionSessionId).toBe('sess-2');
  });

  it('treats task_form_ready as ready when respond returns payload without question', async () => {
    const { interactionRespond } = await import('../../services/api');
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    useTaskFlowStore.setState({
      interactionSessionId: 'sess-3',
      interactionRound: 1,
      entryMode: 'documents',
      interactionMessages: [
        { id: 'm1', role: 'assistant', text: '请回答问题', createdAtMs: Date.now() },
      ],
      taskForm: null,
      taskFormPayload: null,
    } as never);

    vi.mocked(interactionRespond).mockResolvedValue({
      ready: false,
      task_form_ready: true,
      task_form: {
        goal: 'g',
        disease: 'd',
        country: 'CN',
        language: 'en',
      },
      task_form_payload: { goal: 'g', disease: 'd' },
      request_payload: { target: 'g', disease: 'd' },
      question: null,
      round: 2,
    });

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('澄清回答'), { target: { value: '补充回答' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(useTaskFlowStore.getState().taskForm).toEqual({
        goal: 'g',
        disease: 'd',
        country: 'CN',
        language: 'en',
      });
    });
    expect(useTaskFlowStore.getState().taskFormPayload).toEqual({ goal: 'g', disease: 'd' });
    expect(screen.getByText(/任务表单已就绪/i)).toBeInTheDocument();
  });

  it('uses clarification_question when question is absent on respond response', async () => {
    const { interactionRespond } = await import('../../services/api');
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    useTaskFlowStore.setState({
      interactionSessionId: 'sess-4',
      interactionRound: 1,
      entryMode: 'documents',
      interactionMessages: [{ id: 'm1', role: 'assistant', text: '请回答问题', createdAtMs: Date.now() }],
      taskForm: null,
      taskFormPayload: null,
    } as never);

    const response: InteractionRespondResponse & { clarification_question: string; needs_clarification: boolean } = {
      ready: false,
      task_form_ready: false,
      task_form: null,
      task_form_payload: null,
      request_payload: null,
      question: null,
      clarification_question: '请补充样本数量',
      needs_clarification: true,
      round: 2,
    };
    vi.mocked(interactionRespond).mockResolvedValue(response);

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('澄清回答'), { target: { value: '补充回答' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('请补充样本数量')).toBeInTheDocument();
  });

  it('ignores task_form when neither ready nor task_form_ready is true', async () => {
    const { interactionRespond } = await import('../../services/api');
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    useTaskFlowStore.setState({
      interactionSessionId: 'sess-5',
      interactionRound: 1,
      entryMode: 'documents',
      interactionMessages: [{ id: 'm1', role: 'assistant', text: '请回答问题', createdAtMs: Date.now() }],
      taskForm: null,
      taskFormPayload: null,
    } as never);

    vi.mocked(interactionRespond).mockResolvedValue({
      ready: false,
      task_form_ready: false,
      task_form: {
        goal: 'g',
        disease: 'd',
        country: 'CN',
        language: 'en',
      },
      task_form_payload: null,
      request_payload: null,
      question: null,
      round: 2,
    });

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('澄清回答'), { target: { value: '补充回答' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(useTaskFlowStore.getState().taskForm).toBeNull();
    });
    expect(screen.getByText(/后端未返回问题也未返回任务表单/i)).toBeInTheDocument();
  });

  it('passes AbortSignal options when sending interaction requests', async () => {
    const { interactionRespond, interactionStart } = await import('../../services/api');
    const { useTaskFlowStore } = await import('../../store/useTaskFlowStore');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    vi.mocked(interactionStart).mockResolvedValue({
      session_id: 'sess-6',
      ready: false,
      task_form: null,
      question: '请补充证据来源',
      round: 1,
    });
    vi.mocked(interactionRespond).mockResolvedValue({
      ready: false,
      task_form: null,
      question: '请补充样本数量',
      round: 2,
    });

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '解析文档' }));
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));

    await screen.findByText('请补充证据来源');

    const startCall = vi.mocked(interactionStart).mock.calls[0];
    expect(startCall?.[1]?.signal).toBeInstanceOf(AbortSignal);

    fireEvent.change(screen.getByLabelText('澄清回答'), { target: { value: '补充回答' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await screen.findByText('请补充样本数量');

    const respondCall = vi.mocked(interactionRespond).mock.calls[0];
    expect(respondCall?.[1]?.signal).toBeInstanceOf(AbortSignal);

    useTaskFlowStore.getState();
  });

  it('aborts in-flight start request when restarting', async () => {
    const { interactionStart } = await import('../../services/api');
    const { AgentClarificationChat } = await import('./agent-clarification-chat');

    let capturedSignal: AbortSignal | undefined;
    vi.mocked(interactionStart).mockImplementation((_payload, options) => {
      capturedSignal = options?.signal;
      return new Promise(() => {});
    });

    render(
      <AgentClarificationChat
        draft={{ goal: 'g', disease: 'd', country: 'CN', language: 'en' }}
        userInput="Goal: g\nDisease: d\nCountry: CN\nLanguage: en"
        busy={false}
        setBusy={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '解析文档' }));
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));

    await waitFor(() => {
      expect(capturedSignal).toBeDefined();
    });
    expect(capturedSignal?.aborted).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Restart' }));

    expect(capturedSignal?.aborted).toBe(true);
  });
});

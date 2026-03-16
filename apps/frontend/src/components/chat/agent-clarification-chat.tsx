import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { interactionRespond, interactionStart } from '../../services/api';
import { ApiError } from '../../services/http';
import { useScrollToBottom } from '../../hooks/useScrollToBottom';
import { useTaskFlowStore } from '../../store/useTaskFlowStore';
import { useToastStore } from '../../store/useToastStore';

import type { Dispatch, SetStateAction } from 'react';
import type { TaskFormStructured } from '../../types/api';
import type { ChatMessage, ChatRole } from './types';

import './agent-clarification-chat.css';

function makeMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createMessage(role: ChatRole, text: string): ChatMessage {
  return {
    id: makeMessageId(),
    role,
    text,
    createdAtMs: Date.now()
  };
}

type AgentClarificationChatProps = {
  draft: TaskFormStructured;
  userInput: string;
  busy: boolean;
  setBusy: Dispatch<SetStateAction<boolean>>;
};

export const AgentClarificationChat: React.FC<AgentClarificationChatProps> = ({ draft, userInput, busy, setBusy }) => {
  const navigate = useNavigate();
  const toast = useToastStore();
  const { taskForm, interactionSessionId, interactionRound, entryMode, setTaskForm, setInteraction, setEntryMode } = useTaskFlowStore();

  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [composerText, setComposerText] = useState('');

  const canClarify = interactionRound < 2;
  const requiredOk = Boolean(draft.goal.trim() && draft.disease.trim());

  const lastAssistantQuestion = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.role === 'assistant') return m.text;
    }
    return null;
  }, [messages]);

  const scrollRef = useScrollToBottom(messages.length);

  const append = (role: ChatRole, text: string) => {
    setMessages((prev) => [...prev, createMessage(role, text)]);
  };

  const clearInteractionAndForm = () => {
    setInteraction(null, 0);
    setTaskForm(null);
  };

  const resetTranscript = () => {
    setMessages([]);
    setComposerText('');
  };

  const restart = () => {
    clearInteractionAndForm();
    setEntryMode(null);
    resetTranscript();
  };

  const chooseDocuments = () => {
    clearInteractionAndForm();
    setEntryMode('documents');
    resetTranscript();
    append('user', '解析文档');
    append('assistant', '好的。请先填写目标与疾病信息，然后点击 Start 进行澄清（最多 2 轮）。');
  };

  const chooseGraph = () => {
    clearInteractionAndForm();
    setEntryMode('graph');
    resetTranscript();
    navigate('/graph');
  };

  const start = async () => {
    if (!entryMode) {
      toast.pushToast({ level: 'warning', title: '请选择入口', message: '请先选择“解析文档”或“检索图谱”', ttlMs: 5000 });
      return;
    }
    if (entryMode !== 'documents') {
      toast.pushToast({ level: 'warning', title: '当前为图谱入口', message: '图谱检索请前往 Graph 页面。', ttlMs: 5000 });
      navigate('/graph');
      return;
    }
    if (!requiredOk) {
      toast.pushToast({ level: 'warning', title: '缺少必填项', message: 'Goal 和 Disease 为必填。', ttlMs: 5000 });
      return;
    }
    if (!canClarify) {
      append('system', '已达到最多澄清轮次（2 轮）。请点击 Restart 重新开始。');
      return;
    }

    setBusy(true);
    try {
      append('user', userInput);
      const res = await interactionStart({ user_input: userInput });
      setInteraction(res.session_id, res.round);
      if (res.question) {
        append('assistant', res.question);
      }
      if (res.task_form) {
        setTaskForm(res.task_form);
        append('system', '任务表单已就绪：可以进入下一步（上传/检索文献）。');
      }
      if (!res.question && !res.task_form) {
        append('error', '后端未返回问题也未返回任务表单。请点击 Restart 重新开始。');
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to start interaction';
      toast.pushToast({ level: 'error', title: 'Interaction failed', message: msg, ttlMs: 8000 });
      append('error', msg);
    } finally {
      setBusy(false);
    }
  };

  const respond = async () => {
    if (!interactionSessionId) {
      append('system', '请先点击 Start 开始澄清。');
      return;
    }
    if (messages.length === 0) {
      append('system', '会话仍在进行，但聊天记录已丢失（可能是你离开了页面）。请点击 Restart 重新开始。');
      return;
    }
    if (!canClarify) {
      append('system', '已达到最多澄清轮次（2 轮）。请点击 Restart 重新开始。');
      return;
    }
    if (taskForm) {
      append('system', '任务表单已就绪：可以进入下一步（上传/检索文献）。');
      return;
    }
    if (!composerText.trim()) {
      toast.pushToast({ level: 'warning', title: '回答为空', message: '请先输入对问题的回答。', ttlMs: 5000 });
      return;
    }

    const answer = composerText;
    setComposerText('');
    append('user', answer);

    setBusy(true);
    try {
      const res = await interactionRespond({ session_id: interactionSessionId, user_response: answer });
      setInteraction(interactionSessionId, res.round);

      if (res.question) {
        append('assistant', res.question);
      }
      if (res.task_form) {
        setTaskForm(res.task_form);
        append('system', '任务表单已就绪：可以进入下一步（上传/检索文献）。');
      }
      if (!res.question && !res.task_form) {
        append('error', '后端未返回问题也未返回任务表单。请点击 Restart 重新开始。');
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail ?? err.message : 'Failed to respond';
      toast.pushToast({ level: 'error', title: 'Interaction failed', message: msg, ttlMs: 8000 });
      append('error', msg);
    } finally {
      setBusy(false);
    }
  };

  const showStart = !interactionSessionId && !taskForm;
  const showComposer = Boolean(interactionSessionId) && !taskForm;
  const transcriptMissing = showComposer && messages.length === 0;

  const lastMessageRole: ChatRole | null = messages.length ? messages[messages.length - 1]!.role : null;

  useEffect(() => {
    if (busy) return;
    if (!showComposer) return;
    if (transcriptMissing) return;
    if (lastMessageRole !== 'assistant') return;
    composerRef.current?.focus();
  }, [busy, lastMessageRole, showComposer, transcriptMissing]);

  return (
    <div className="agent-chat">
      <div className="agent-chat__header">
        <div>
          <h2 className="agent-chat__title" style={{ margin: 0 }}>
            Clarification Chat
          </h2>
          {lastAssistantQuestion ? (
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              Latest question ready.
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              {showStart ? 'Start and answer up to 2 rounds.' : 'Answer the assistant question to continue.'}
            </div>
          )}
        </div>
        <div className="agent-chat__meta" aria-label="Chat meta">
          <div className="agent-chat__pill" aria-live="polite" aria-atomic="true">
            Rounds: {interactionRound}/2
          </div>
          {entryMode ? <div className="agent-chat__pill">Mode: {entryMode}</div> : <div className="agent-chat__pill">Mode: not set</div>}
          {taskForm ? <div className="agent-chat__pill">Task form: ready</div> : <div className="agent-chat__pill">Task form: pending</div>}
        </div>
      </div>

      <div
        ref={scrollRef}
        className="agent-chat__transcript"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-atomic="false"
        aria-label="Clarification transcript"
      >
        {showStart && messages.length === 0 ? (
          <div className="agent-chat__row" data-role="assistant">
            <div className="agent-chat__bubble" data-role="assistant">
              在开始之前，你想进行哪种工作？
              {entryMode ? (
                <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                  当前选择：<b>{entryMode === 'documents' ? '解析文档' : '检索图谱'}</b>
                  <button type="button" className="agent-chat__link" onClick={() => setEntryMode(null)} disabled={busy}>
                    重新选择
                  </button>
                </div>
              ) : null}
              <div className="agent-chat__quick-replies" role="group" aria-label="Entry mode">
                <button type="button" className="agent-chat__chip" onClick={chooseDocuments} disabled={busy}>
                  解析文档
                </button>
                <button type="button" className="agent-chat__chip" onClick={chooseGraph} disabled={busy}>
                  检索图谱
                </button>
              </div>
            </div>
          </div>
        ) : null}
        {transcriptMissing ? (
          <div className="agent-chat__row" data-role="system">
            <div className="agent-chat__bubble" data-role="system" id="agent-chat-transcript-missing">
              会话仍在进行，但聊天记录已丢失（可能是你离开了页面）。请点击 Restart 重新开始。
            </div>
          </div>
        ) : null}
        {messages.length === 0 && entryMode === 'documents' ? (
          <div className="agent-chat__empty">
            请先填写 <b>Goal</b> 和 <b>Disease</b>，然后点击 <b>Start</b> 开始澄清。我们会将结构化表单格式化为首条消息发送给后端。
          </div>
        ) : null}
        {messages.map((m) => (
          <div key={m.id} className="agent-chat__row" data-role={m.role}>
            <div className="agent-chat__bubble" data-role={m.role}>
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <div className="agent-chat__composer">
        <textarea
          className="agent-chat__textarea"
          aria-label="澄清回答"
          name="clarification_response"
          autoComplete="off"
          ref={composerRef}
          value={composerText}
          onChange={(e) => setComposerText(e.target.value)}
          rows={3}
          placeholder={showComposer ? 'Type your answer…' : 'Start clarification to enable answering…'}
          disabled={busy || !showComposer || transcriptMissing}
          aria-describedby={transcriptMissing ? 'agent-chat-transcript-missing' : undefined}
        />
        <div className="agent-chat__actions">
          {showStart ? (
            <button
              type="button"
              className="agent-chat__btn agent-chat__btn--primary"
              onClick={start}
              disabled={busy || !canClarify || !requiredOk || entryMode !== 'documents'}
              title={
                !entryMode
                  ? 'Please choose a mode first'
                  : entryMode !== 'documents'
                    ? 'Graph mode uses /graph'
                    : !requiredOk
                      ? 'Goal and disease are required'
                      : undefined
              }
            >
              Start
            </button>
          ) : null}
          {showComposer ? (
            <button type="button" className="agent-chat__btn" onClick={respond} disabled={busy || !canClarify || transcriptMissing}>
              Send
            </button>
          ) : null}
          <button type="button" className="agent-chat__btn agent-chat__btn--danger" onClick={restart} disabled={busy}>
            Restart
          </button>
        </div>
      </div>

      {!canClarify && !taskForm ? <div className="muted" style={{ fontSize: 12 }}>Max clarification rounds reached.</div> : null}
    </div>
  );
};

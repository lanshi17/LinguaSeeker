"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import type { ChatMessage } from "../stores/taskFlowStore";

interface ClarificationChatProps {
  messages: ChatMessage[];
  onSend: (answer: string) => void;
  isSending: boolean;
  disabled?: boolean;
}

export function ClarificationChat({
  messages,
  onSend,
  isSending,
  disabled,
}: ClarificationChatProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  }

  return (
    <Card className="flex h-[400px] flex-col">
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Agent Clarification
      </h3>

      {/* Messages */}
      <div className="flex-1 space-y-3 overflow-y-auto">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-primary-100 text-primary-900"
                  : msg.role === "error"
                    ? "bg-red-50 text-red-800"
                    : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.role === "assistant" && (
                <span className="mb-1 block text-xs font-medium text-gray-500">
                  ACMG Agent
                </span>
              )}
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      {!disabled && (
        <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
          <Input
            placeholder="Type your answer..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSending}
          />
          <Button type="submit" size="sm" loading={isSending} disabled={!input.trim()}>
            Send
          </Button>
        </form>
      )}
    </Card>
  );
}

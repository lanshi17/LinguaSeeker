"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";

interface ChatComposerProps {
  onSend: (content: string) => void;
  isSending?: boolean;
  disabled?: boolean;
}

export function ChatComposer({ onSend, isSending, disabled }: ChatComposerProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 border-t border-gray-200 p-4">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type a message..."
        disabled={disabled || isSending}
        className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
      />
      <Button type="submit" size="sm" loading={isSending} disabled={!input.trim()}>
        Send
      </Button>
    </form>
  );
}

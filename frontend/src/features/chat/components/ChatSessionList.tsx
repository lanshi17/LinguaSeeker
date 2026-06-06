"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useChatSessions } from "../hooks/useChatSessions";

interface ChatSessionListProps {
  processingRunId: string;
}

export function ChatSessionList({ processingRunId }: ChatSessionListProps) {
  const { sessions, isLoading, createSession, isCreating } =
    useChatSessions(processingRunId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Chat Sessions</h2>
        <button
          onClick={() => createSession()}
          disabled={isCreating}
          className="cursor-pointer text-sm font-medium text-primary-600 hover:underline"
        >
          {isCreating ? "Creating..." : "+ New Session"}
        </button>
      </div>

      {sessions.length === 0 ? (
        <p className="py-10 text-center text-sm text-gray-500">
          No chat sessions yet.
        </p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <Link key={s.session_id} href={`/chat/${s.session_id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">
                    Session {s.session_id.slice(0, 8)}
                  </span>
                  <span className="text-xs text-gray-400">
                    {s.message_count} messages
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {new Date(s.created_at).toLocaleString()}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

interface DocumentResyncFormProps {
  onResync: (documentId: string) => void;
  isResyncing?: boolean;
}

export function DocumentResyncForm({
  onResync,
  isResyncing,
}: DocumentResyncFormProps) {
  const [docId, setDocId] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (docId.trim()) onResync(docId.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3">
      <Input
        label="Document ID"
        placeholder="UUID"
        value={docId}
        onChange={(e) => setDocId(e.target.value)}
      />
      <Button type="submit" size="sm" loading={isResyncing} disabled={!docId.trim()}>
        Resync
      </Button>
    </form>
  );
}

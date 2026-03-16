export type ChatRole = 'assistant' | 'user' | 'system' | 'error';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  createdAtMs: number;
};

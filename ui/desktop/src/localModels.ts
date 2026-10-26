export const LOCAL_CHAT_MODELS = [
  { provider: 'ollama', model: 'qwen3.5:9b-q4_K_M', label: 'Qwen 9B' },
  { provider: 'ollama', model: 'gemma4:12b-it-q4_K_M', label: 'Gemma 12B' },
] as const;

export const DEFAULT_LOCAL_MODEL = 'qwen3.5:9b-q4_K_M';
export const LOCAL_CONTEXT_LIMIT = 16384;

export type Passage = {
  id: number;
  source: string | null;
  content: string;
};

export type Answer = {
  answer: string;
  sources: Passage[];
};

export async function ask(question: string, sessionId: string): Promise<Answer> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
  }).catch(() => {
    throw new Error('Could not reach Lighthouse. Try again in a moment.');
  });

  if (response.status === 422) throw new Error('Enter a question of up to 4,000 characters.');
  if (!response.ok) throw new Error('Lighthouse is unavailable. Check the local API, PostgreSQL and Ollama.');

  return response.json();
}

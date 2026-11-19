import { StrictMode, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import Markdown from 'react-markdown';
import { ask } from './api';
import type { Answer } from './api';
import { groupSources, SourceDocuments, Sources } from './Sources';
import './styles.css';

type Turn = Answer & { id: string; question: string };
type Chat = { id: string; turns: Turn[] };

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function Workspace() {
  const [chatId, setChatId] = useState<string>(() => crypto.randomUUID());
  const [chats, setChats] = useState<Chat[]>([]);
  const [question, setQuestion] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [error, setError] = useState('');
  const [sourceTurnId, setSourceTurnId] = useState<string | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pendingTurn = useRef<HTMLDivElement>(null);

  const turns = chats.find((chat) => chat.id === chatId)?.turns ?? [];
  const sourceTurn = turns.find((turn) => turn.id === sourceTurnId) ?? turns.at(-1);
  const sources = groupSources(sourceTurn?.sources ?? []);
  const hasConversation = turns.length > 0 || Boolean(pendingQuestion);

  useEffect(() => {
    if (pendingQuestion) pendingTurn.current?.scrollIntoView({ block: 'start' });
  }, [pendingQuestion]);

  function selectChat(id: string) {
    setChatId(id);
    setQuestion('');
    setError('');
    setSourceTurnId(null);
    setSourcesOpen(false);
    setNavigationOpen(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || pendingQuestion) return;

    setPendingQuestion(prompt);
    setQuestion('');
    setError('');
    try {
      const result = await ask(prompt, chatId);
      const turn = { id: crypto.randomUUID(), question: prompt, ...result };
      setChats((previous) => {
        const current = previous.find((chat) => chat.id === chatId);
        return [
          { id: chatId, turns: [...(current?.turns ?? []), turn] },
          ...previous.filter((chat) => chat.id !== chatId),
        ];
      });
      setSourceTurnId(turn.id);
    } catch (failure) {
      setQuestion(prompt);
      setError(failure instanceof Error ? failure.message : 'Something went wrong. Please try again.');
    } finally {
      setPendingQuestion('');
    }
  }

  return (
    <div className="shell">
      <aside id="navigation" className={navigationOpen ? 'sidebar is-open' : 'sidebar'} aria-label="Workspace navigation">
        <div className="brand">
          <img src="/lighthouse.svg" width="44" height="44" alt="" />
          <span>Lighthouse Lab</span>
        </div>
        <button
          className="new-chat"
          type="button"
          onClick={() => { selectChat(crypto.randomUUID()); input.current?.focus(); }}
          disabled={Boolean(pendingQuestion)}
        >
          <span aria-hidden="true">+</span> New chat
        </button>
        <div className="history">
          <h2>Conversations</h2>
          {chats.length === 0 && <p>Your chats will appear here.</p>}
          {chats.map((chat) => (
            <button
              className="history-item"
              key={chat.id}
              type="button"
              aria-current={chat.id === chatId ? 'true' : undefined}
              onClick={() => selectChat(chat.id)}
              disabled={Boolean(pendingQuestion)}
            >
              {chat.turns[0].question}
            </button>
          ))}
        </div>
        <img className="sidebar-art" src="/lighthouse-coast.jpg" alt="" />
      </aside>

      <header className="masthead">
        <button
          className="toolbar-button menu"
          type="button"
          aria-controls="navigation"
          aria-expanded={navigationOpen}
          onClick={() => { setNavigationOpen(!navigationOpen); setSourcesOpen(false); }}
        >
          Chats
        </button>
        <h1>Conversation</h1>
        <button
          className="toolbar-button mobile-sources"
          type="button"
          aria-controls="source-panel"
          aria-expanded={sourcesOpen}
          onClick={() => { setSourcesOpen(!sourcesOpen); setNavigationOpen(false); }}
        >
          Documents
        </button>
      </header>

      <main className={hasConversation ? 'chat active' : 'chat'}>
        {hasConversation ? (
          <section className="transcript" aria-label="Conversation">
            <div className="column turns" key={chatId}>
              {turns.map((turn) => {
                const documents = groupSources(turn.sources);
                return (
                  <article className="turn" key={turn.id}>
                    <p className="question">{turn.question}</p>
                    <div className="assistant">
                      <img src="/lighthouse.svg" width="36" height="36" alt="" />
                      <div className="answer" aria-label="Lighthouse response">
                        <Markdown>{turn.answer}</Markdown>
                        {documents.length > 0 && (
                          <details
                            className="inline-sources"
                            onToggle={(event) => {
                              if (event.currentTarget.open) setSourceTurnId(turn.id);
                            }}
                          >
                            <summary className="sources-toggle">Sources · {documents.length}</summary>
                            <Sources documents={documents} />
                          </details>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
              {pendingQuestion && (
                <div className="turn" ref={pendingTurn}>
                  <p className="question">{pendingQuestion}</p>
                  <p className="pending" role="status">Searching and preparing a response…</p>
                </div>
              )}
            </div>
          </section>
        ) : (
          <div className="welcome">
            <img src="/lighthouse.svg" width="58" height="58" alt="" />
            <h2>{greeting()}</h2>
          </div>
        )}

        <form className="column composer" onSubmit={submit}>
          <div className="composer-row">
            <input
              ref={input}
              aria-label="Ask anything"
              type="text"
              placeholder="Ask anything…"
              value={question}
              maxLength={4000}
              readOnly={Boolean(pendingQuestion)}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button type="submit" disabled={Boolean(pendingQuestion) || !question.trim()}>Send</button>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
        </form>
      </main>

      <aside id="source-panel" className={sourcesOpen ? 'source-panel is-open' : 'source-panel'} aria-labelledby="source-title">
        <div className="source-header">
          <h2 id="source-title">Original documents{sources.length > 0 && <span>{sources.length}</span>}</h2>
          <button className="toolbar-button mobile-sources" type="button" onClick={() => setSourcesOpen(false)}>Close</button>
        </div>
        {sourceTurn && <p className="source-question">{sourceTurn.question}</p>}
        {sources.length ? (
          <>
            <SourceDocuments documents={sources} />
            <p className="source-empty">Original links are unavailable for this corpus.</p>
          </>
        ) : (
          <p className="source-empty">{sourceTurn ? 'No documents were retrieved.' : 'Documents appear here after a response.'}</p>
        )}
      </aside>
    </div>
  );
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing application root');

createRoot(root).render(<StrictMode><Workspace /></StrictMode>);

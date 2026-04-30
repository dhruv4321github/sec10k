/**
 * ChatInterface.jsx — RAG question + cited answer.
 *
 * History persistence
 * -------------------
 * Chat sessions are persisted to localStorage so navigating between tabs
 * (or refreshing the browser) doesn't lose your conversations. A sidebar
 * lists past sessions; you can switch between them or start a new one.
 *
 * Each session contains: { id, title, created_at, messages[] }.
 * Each message contains: { role, content, sources?, model?, error?, timestamp }.
 *
 * The sidebar shows the title (auto-derived from the first question) plus
 * the relative time. localStorage is keyed under "sec10k.chat_sessions".
 *
 * The top-K knob has been removed — it's not in the assignment spec.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { askQuestion } from '../services/api';

const SUGGESTIONS = [
  { q: 'What are the top business risks described by the company?',                section: 'Risk Factors' },
  { q: 'What does the company say about revenue growth or business performance?', section: "Management's Discussion and Analysis" },
  { q: 'What are the main business segments or operating priorities?',             section: 'Business' },
  { q: 'Compare risk factors between two companies.',                              section: '' },
  { q: 'What themes appear repeatedly in management discussion?',                  section: "Management's Discussion and Analysis" },
];

const SECTIONS = [
  '',
  'Business',
  'Risk Factors',
  "Management's Discussion and Analysis",
  'Financial Statements',
];

const STORAGE_KEY = 'sec10k.chat_sessions';

// ──────────────────────────── localStorage ────────────────────────────

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    // Revive timestamps
    return parsed.map((s) => ({
      ...s,
      created_at: new Date(s.created_at),
      messages: (s.messages || []).map((m) => ({ ...m, timestamp: new Date(m.timestamp) })),
    }));
  } catch {
    return [];
  }
}

function saveSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch (err) {
    console.warn('Failed to persist chat sessions:', err);
  }
}

function makeSession() {
  return {
    id: `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    title: 'New conversation',
    created_at: new Date(),
    messages: [],
  };
}

// Format relative time (e.g. "2m ago", "3h ago", "Yesterday")
function relativeTime(d) {
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 2) return 'Yesterday';
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

// ──────────────────────────── Citation rendering ────────────────────────────

function AnswerText({ text, citationsCount }) {
  const parts = useMemo(() => {
    const out = [];
    const re = /\[(\d+)\]/g;
    let last = 0; let m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) out.push({ kind: 'text', value: text.slice(last, m.index) });
      const n = parseInt(m[1], 10);
      out.push(n >= 1 && n <= citationsCount
        ? { kind: 'cite', value: n }
        : { kind: 'text', value: m[0] });
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push({ kind: 'text', value: text.slice(last) });
    return out;
  }, [text, citationsCount]);

  return (
    <>
      {parts.map((p, i) => p.kind === 'text' ? (
        <span key={i}>{p.value}</span>
      ) : (
        <a
          key={i} href={`#cite-${p.value}`} className="cite-chip"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(`cite-${p.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }}
        >{p.value}</a>
      ))}
    </>
  );
}

// ──────────────────────────── Main component ────────────────────────────

function ChatInterface({ documents }) {
  const ready = documents.filter((d) => d.status === 'ready');
  const companies = Array.from(new Set(ready.map((d) => d.company)));

  const [sessions, setSessions] = useState(() => {
    const loaded = loadSessions();
    return loaded.length > 0 ? loaded : [makeSession()];
  });
  const [activeId, setActiveId] = useState(() => {
    const loaded = loadSessions();
    return loaded.length > 0 ? loaded[0].id : sessions[0]?.id;
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [companyFilter, setCompanyFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');

  const messagesEndRef = useRef(null);

  // Persist whenever sessions change
  useEffect(() => { saveSessions(sessions); }, [sessions]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessions, activeId, loading]);

  const activeSession = sessions.find((s) => s.id === activeId) || sessions[0];

  const updateSession = (id, updater) => {
    setSessions((prev) => prev.map((s) => s.id === id ? updater(s) : s));
  };

  const newSession = () => {
    const s = makeSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
    setInput('');
  };

  const deleteSession = (id) => {
    if (!window.confirm('Delete this conversation?')) return;
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id);
      if (filtered.length === 0) {
        const fresh = makeSession();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (id === activeId) setActiveId(filtered[0].id);
      return filtered;
    });
  };

  const ask = async (questionOverride = null) => {
    const query = (questionOverride ?? input).trim();
    if (!query || loading) return;

    const userMsg = { role: 'user', content: query, timestamp: new Date() };
    updateSession(activeSession.id, (s) => ({
      ...s,
      // Auto-title from first user message
      title: s.messages.length === 0 ? (query.length > 60 ? query.slice(0, 60) + '…' : query) : s.title,
      messages: [...s.messages, userMsg],
    }));
    setInput('');
    setLoading(true);

    try {
      const res = await askQuestion(query, {
        companyFilter: companyFilter || null,
        sectionFilter: sectionFilter || null,
      });
      const aiMsg = {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources,
        model: res.data.model_used,
        timestamp: new Date(),
      };
      updateSession(activeSession.id, (s) => ({ ...s, messages: [...s.messages, aiMsg] }));
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      updateSession(activeSession.id, (s) => ({
        ...s,
        messages: [...s.messages, {
          role: 'assistant',
          content: typeof detail === 'string' ? detail : 'Sorry, an error occurred.',
          error: true,
          timestamp: new Date(),
        }],
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  };

  if (ready.length === 0) {
    return (
      <div className="panel">
        <h2>Ask</h2>
        <p className="empty-state">
          Ingest at least one filing and wait for it to reach
          <span className="status-badge status-ready" style={{ margin: '0 0.4rem' }}>Ready</span>
          before asking a question.
        </p>
      </div>
    );
  }

  return (
    <div className="chat-layout-3col">
      {/* Sessions sidebar */}
      <aside className="chat-sessions">
        <div className="sessions-header">
          <h3>Conversations</h3>
          <button className="btn-new-chat" onClick={newSession} title="Start a new conversation">
            + New
          </button>
        </div>
        <ul className="sessions-list">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setActiveId(s.id)}
                className={`session-item ${activeId === s.id ? 'active' : ''}`}
              >
                <div className="session-title">{s.title}</div>
                <div className="session-meta">
                  <span>{relativeTime(new Date(s.created_at))}</span>
                  <span className="session-msgs">{s.messages.length} msg</span>
                </div>
              </button>
              <button
                className="session-delete"
                onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                title="Delete this conversation"
              >×</button>
            </li>
          ))}
        </ul>
      </aside>

      {/* Filters rail */}
      <aside className="chat-rail">
        <h3>Retrieval Filters</h3>
        <div className="filter-row">
          <label>Company</label>
          <select value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)}>
            <option value="">— Any —</option>
            {companies.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="filter-row">
          <label>Section</label>
          <select value={sectionFilter} onChange={(e) => setSectionFilter(e.target.value)}>
            {SECTIONS.map((s) => <option key={s} value={s}>{s || '— Any —'}</option>)}
          </select>
        </div>
        <p className="filter-hint">
          When <strong>Company</strong> is "Any" and multiple filings are
          ingested, the server retrieves per-company so comparisons see
          evidence from every company.
        </p>
      </aside>

      {/* Chat panel */}
      <div className="panel chat-panel">
        <h2>Ask</h2>
        <p className="panel-description">
          Questions are answered using only retrieved context from your ingested filings, with inline citations.
        </p>

        <div className="chat-messages">
          {activeSession.messages.length === 0 && (
            <div className="empty-chat">
              <span className="chat-icon">💬</span>
              <p>Ask a question about your ingested filings.</p>
              <div className="example-queries">
                <p><strong>Example questions:</strong></p>
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setSectionFilter(s.section || '');
                      setCompanyFilter('');
                      ask(s.q);
                    }}
                  >"{s.q}"</button>
                ))}
              </div>
            </div>
          )}

          {activeSession.messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-header">
                <span className="message-role">
                  {msg.role === 'user' ? '👤 You' : '🤖 Analyst'}
                </span>
                <span className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className={`message-content ${msg.error ? 'error' : ''}`}>
                {msg.role === 'assistant' && !msg.error ? (
                  <AnswerText text={msg.content} citationsCount={msg.sources?.length || 0} />
                ) : msg.content}
              </div>

              {msg.sources && msg.sources.length > 0 && (
                <div className="sources">
                  <p className="sources-label">📎 Sources ({msg.sources.length})</p>
                  {msg.sources.map((src, j) => (
                    <div key={src.chunk_id} id={`cite-${j + 1}`} className="source-card">
                      <div className="source-header">
                        <span className="cite-num">[{j + 1}]</span>
                        <strong>{src.company}</strong>
                        <span className="source-section">§ {src.section}</span>
                        <span className="relevance">rrf {src.score.toFixed(4)}</span>
                      </div>
                      <p className="source-preview">{src.snippet}</p>
                    </div>
                  ))}
                </div>
              )}

              {msg.role === 'assistant' && msg.model && (
                <div className="message-footer">model · {msg.model}</div>
              )}
            </div>
          ))}

          {loading && (
            <div className="message assistant">
              <div className="message-header">
                <span className="message-role">🤖 Analyst</span>
              </div>
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your ingested filings…"
            rows={2}
            disabled={loading}
          />
          <button
            className="btn-send"
            onClick={() => ask()}
            disabled={!input.trim() || loading}
            title="Send (Enter)"
          >
            {loading ? '⏳' : '➤'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;

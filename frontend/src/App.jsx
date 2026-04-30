/**
 * App.jsx — Tab-based shell for the three views.
 *
 *   Filings  — ingest a 10-K, see status, browse the list
 *   Sections — read the extracted Items
 *   Ask      — RAG question with cited answer
 *
 * Documents are polled every 4s so users see the status pill update
 * (pending → parsing → embedding → ready) without manual refresh.
 */

import React, { useState, useEffect, useCallback } from 'react';
import DocumentUpload from './components/DocumentUpload';
import SectionsView from './components/SectionsView';
import ChatInterface from './components/ChatInterface';
import { getDocuments } from './services/api';

const TABS = [
  { id: 'documents', label: '📄 Filings' },
  { id: 'sections',  label: '📚 Sections' },
  { id: 'chat',      label: '💬 Ask' },
];

function App() {
  const [activeTab, setActiveTab] = useState('documents');
  const [documents, setDocuments] = useState([]);

  const refreshDocuments = useCallback(async () => {
    try {
      const res = await getDocuments();
      setDocuments(res.data);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    }
  }, []);

  // Initial load
  useEffect(() => { refreshDocuments(); }, [refreshDocuments]);

  // Background polling — keeps the status pill fresh while embedding runs
  useEffect(() => {
    const t = setInterval(refreshDocuments, 4000);
    return () => clearInterval(t);
  }, [refreshDocuments]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>📑 SEC 10-K Analyst</h1>
          <p>Ingest annual reports, browse extracted sections, and ask questions with retrieval-augmented generation.</p>
        </div>
      </header>

      <nav className="tab-nav">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="main-content">
        {activeTab === 'documents' && (
          <DocumentUpload documents={documents} onRefresh={refreshDocuments} />
        )}
        {activeTab === 'sections' && (
          <SectionsView documents={documents} />
        )}
        {activeTab === 'chat' && (
          <ChatInterface documents={documents} />
        )}
      </main>

      <footer className="app-footer">
        <p>SEC 10-K Analyst · FastAPI · Postgres + pgvector · OpenAI</p>
      </footer>
    </div>
  );
}

export default App;

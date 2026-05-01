/**
 * DocumentUpload.jsx — Filings management.
 *
 * Three quick-add presets for the suggested filings (AAPL, MSFT, NVDA).
 * No free-form URL form (per requirements).
 *
 * Loading UX:
 *   - The clicked preset shows an inline spinner while submitting.
 *   - After submission, the new document appears in the list. While its status
 *     is pending/parsing/embedding, the card itself shows a yellow banner with
 *     a spinner — so the user always knows work is happening.
 *   - Statuses auto-refresh every 4s from the parent.
 */

import React, { useState } from 'react';
import { ingestDocument, deleteDocument } from '../services/api';

const PRESETS = [
  {
    company: 'Apple Inc.', ticker: 'AAPL', fiscal_year: 2025, icon: '🍎',
    url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
  },
  {
    company: 'Microsoft Corporation', ticker: 'MSFT', fiscal_year: 2025, icon: '🪟',
    url: 'https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm',
  },
  {
    company: 'NVIDIA Corporation', ticker: 'NVDA', fiscal_year: 2025, icon: '🟢',
    url: 'https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm',
  },
];

const PROCESSING_STATUSES = new Set(['pending', 'parsing', 'embedding']);

function statusLabel(status) {
  switch (status) {
    case 'pending':   return 'Queued';
    case 'parsing':   return 'Parsing';
    case 'embedding': return 'Embedding';
    case 'ready':     return 'Ready';
    case 'error':     return 'Error';
    default:          return status;
  }
}

function statusClass(status) {
  if (status === 'ready') return 'status-ready';
  if (status === 'error') return 'status-error';
  return 'status-processing';
}

function DocumentUpload({ documents, onRefresh }) {
  const [submittingTicker, setSubmittingTicker] = useState(null);
  const [error, setError] = useState(null);

  const submit = async (preset) => {
    setError(null);
    setSubmittingTicker(preset.ticker);
    try {
      await ingestDocument({
        url: preset.url,
        company: preset.company,
        ticker: preset.ticker,
        fiscal_year: preset.fiscal_year,
      });
      await onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : (err.message || 'Ingest failed.'));
    } finally {
      setSubmittingTicker(null);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this filing and all its indexed data?')) return;
    try {
      await deleteDocument(id);
      await onRefresh();
    } catch (err) {
      setError('Failed to delete filing.');
    }
  };

  // Match a preset against an ingested doc by CIK in URL
  const presetIsIngested = (preset) =>
    documents.some((d) => d.cik && preset.url.includes(d.cik));

  return (
    <div className="panel">
      <h2>Filings</h2>
      <p className="panel-description">
        Ingest one of the three suggested SEC 10-K filings. Each filing is fetched, parsed,
        split into chunks, embedded, and indexed for retrieval-augmented question answering.
      </p>

      {/* Quick add */}
      <h3>Add a Filing</h3>
      <div className="preset-grid">
        {PRESETS.map((p) => {
          const ingested = presetIsIngested(p);
          const isSubmitting = submittingTicker === p.ticker;
          return (
            <button
              key={p.ticker}
              className={`preset-card ${ingested ? 'ingested' : ''}`}
              onClick={() => submit(p)}
              disabled={!!submittingTicker || ingested}
            >
              <div className="preset-icon">{p.icon}</div>
              <div className="preset-info">
                <strong>{p.ticker}</strong>
                <span>{p.company}</span>
                <span className="preset-fy">FY {p.fiscal_year}</span>
              </div>
              <div className="preset-action">
                {isSubmitting ? (
                  <span className="spinner-small"></span>
                ) : ingested ? (
                  <span className="preset-check">✓ Added</span>
                ) : (
                  <span className="preset-add">+ Add</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {error && <div className="error-message">⚠ {error}</div>}

      {/* List */}
      <h3 style={{ marginTop: '2rem' }}>Ingested Filings ({documents.length})</h3>
      {documents.length === 0 ? (
        <p className="empty-state">
          No filings yet — click <strong>+ Add</strong> on one of the cards above to get started.
        </p>
      ) : (
        <div className="document-list">
          {documents.map((doc) => {
            const isProcessing = PROCESSING_STATUSES.has(doc.status);
            return (
              <div key={doc.id} className={`document-card ${isProcessing ? 'processing' : ''}`}>
                <div className="doc-info">
                  <span className="doc-icon">📄</span>
                  <div>
                    <h4>
                      {doc.company}
                      {doc.ticker && <span className="doc-ticker">{doc.ticker}</span>}
                    </h4>
                    <p className="doc-meta">
                      {doc.fiscal_year ? `FY ${doc.fiscal_year} · ` : ''}
                      {doc.chunk_count > 0 ? `${doc.chunk_count} chunks · ` : ''}
                      {doc.raw_text_chars > 0 ? `${doc.raw_text_chars.toLocaleString()} chars · ` : ''}
                      added {new Date(doc.created_at).toLocaleString()}
                    </p>

                    {/* Loading banner — visible the entire time the doc is being processed */}
                    {isProcessing && (
                      <div className="doc-processing">
                        <span className="spinner-small"></span>
                        <span>{statusLabel(doc.status)}… this may take a few seconds</span>
                      </div>
                    )}

                    {doc.status === 'error' && doc.error && (
                      <p className="doc-error">⚠ {doc.error}</p>
                    )}
                  </div>
                </div>
                <div className="doc-actions">
                  <span className={`status-badge ${statusClass(doc.status)}`}>
                    {statusLabel(doc.status)}
                  </span>
                  <button
                    className="btn-delete"
                    onClick={() => handleDelete(doc.id)}
                    title="Delete filing"
                  >
                    🗑
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DocumentUpload;

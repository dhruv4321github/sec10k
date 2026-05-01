/**
 * SectionsView.jsx — Browse extracted 10-K sections.
 *
 *   - Left rail: list of ready filings.
 *   - Right pane: that filing's extracted Items (1, 1A, 7, 8) as expandable cards.
 *   - Section text is loaded with the sections list; clicking a card toggles it open.
 */

import React, { useEffect, useState } from 'react';
import { getSections } from '../services/api';

function SectionsView({ documents }) {
  const ready = documents.filter((d) => d.status === 'ready');

  const [selectedId, setSelectedId] = useState(null);
  const [sections, setSections] = useState(null);
  const [loadingSections, setLoadingSections] = useState(false);
  const [openName, setOpenName] = useState(null);

  // Auto-select the first ready doc once they exist
  useEffect(() => {
    if (!selectedId && ready.length > 0) {
      setSelectedId(ready[0].id);
    }
  }, [ready, selectedId]);

  // Load sections whenever the selected doc changes
  useEffect(() => {
    if (!selectedId) {
      setSections(null);
      return;
    }
    setLoadingSections(true);
    setOpenName(null);
    getSections(selectedId)
      .then((res) => setSections(res.data))
      .catch(() => setSections({ sections: [] }))
      .finally(() => setLoadingSections(false));
  }, [selectedId]);

  const openSection = (name) => {
    setOpenName(openName === name ? null : name);
  };

  if (ready.length === 0) {
    return (
      <div className="panel">
        <h2>Sections</h2>
        <p className="empty-state">
          No filings are ready yet. Ingest one in the <strong>Filings</strong> tab and
          wait for its status to reach <span className="status-badge status-ready">Ready</span>.
        </p>
      </div>
    );
  }

  const selectedDoc = ready.find((d) => d.id === selectedId);

  return (
    <div className="sections-panel">
      {/* Left rail */}
      <aside className="sections-rail">
        <h3>Filings</h3>
        <ul className="rail-list">
          {ready.map((d) => (
            <li key={d.id}>
              <button
                onClick={() => setSelectedId(d.id)}
                className={`rail-item ${selectedId === d.id ? 'active' : ''}`}
              >
                <strong>{d.company}</strong>
                <span>{d.ticker}{d.fiscal_year ? ` · FY ${d.fiscal_year}` : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {/* Right pane */}
      <div className="sections-main panel">
        {selectedDoc && (
          <>
            <div className="section-header">
              <div>
                <h2>{selectedDoc.company}</h2>
                <p className="panel-description">
                  10-K · {selectedDoc.fiscal_year ? `FY ${selectedDoc.fiscal_year}` : 'Annual report'}
                  {selectedDoc.raw_text_chars > 0 && ` · ${selectedDoc.raw_text_chars.toLocaleString()} chars parsed`}
                </p>
              </div>
              <a
                href={selectedDoc.source_url}
                target="_blank"
                rel="noreferrer"
                className="source-link"
              >
                View on SEC ↗
              </a>
            </div>

            {loadingSections && (
              <div className="loading-state">
                <span className="spinner-small"></span> Loading sections…
              </div>
            )}

            {sections && !loadingSections && (
              <div className="section-list">
                {sections.sections.length === 0 ? (
                  <p className="empty-state">No sections were extracted from this filing.</p>
                ) : (
                  sections.sections.map((s) => {
                    const isOpen = openName === s.name;
                    return (
                      <article key={s.id} className={`section-card ${isOpen ? 'open' : ''}`}>
                        <button
                          className="section-card-header"
                          onClick={() => openSection(s.name)}
                        >
                          <div className="section-card-title">
                            <span className="section-item-label">{s.item_label}</span>
                            <span className="section-name">{s.name}</span>
                          </div>
                          <div className="section-card-meta">
                            <span className="section-chars">{s.char_count.toLocaleString()} chars</span>
                            <span className={`section-chevron ${isOpen ? 'rotated' : ''}`}>›</span>
                          </div>
                        </button>
                        {isOpen && (
                          <div className="section-card-body">
                            <pre className="section-text">{s.text}</pre>
                          </div>
                        )}
                      </article>
                    );
                  })
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default SectionsView;

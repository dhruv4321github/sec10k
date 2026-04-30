/**
 * api.js — Axios API client.
 *
 * Endpoint paths match the assignment spec exactly:
 *   POST   /documents/ingest
 *   GET    /documents
 *   GET    /documents/{id}
 *   GET    /documents/{id}/sections
 *   GET    /documents/{id}/sections/{name}
 *   DELETE /documents/{id}
 *   POST   /questions/ask
 *   POST   /analysis-jobs              (optional)
 *   GET    /analysis-jobs/{id}         (optional)
 */

import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ── Documents ──────────────────────────────────

export const ingestDocument = (payload) =>
  api.post('/documents/ingest', payload);

export const getDocuments = () => api.get('/documents');

export const getDocument = (id) => api.get(`/documents/${id}`);

export const deleteDocument = (id) => api.delete(`/documents/${id}`);

export const getSections = (id) => api.get(`/documents/${id}/sections`);

export const getSection = (id, name) =>
  api.get(`/documents/${id}/sections/${encodeURIComponent(name)}`);

// ── Questions (RAG) ────────────────────────────

export const askQuestion = (query, opts = {}) =>
  api.post('/questions/ask', {
    query,
    company_filter: opts.companyFilter || null,
    section_filter: opts.sectionFilter || null,
  });

// ── Analysis jobs (optional) ───────────────────

export const submitJob = (kind, payload) =>
  api.post('/analysis-jobs', { kind, payload });

export const getJob = (id) => api.get(`/analysis-jobs/${id}`);

export default api;

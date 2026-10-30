import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { Header } from './components/Header';
import { ChatWorkspace } from './components/ChatWorkspace';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { FileSpreadsheet } from 'lucide-react';
import {
  fetchHealth,
  createJob,
  sendFollowUpMessage,
  getJob,
  subscribeJobEvents,
} from './api';

// Purge legacy persistent localStorage from prior versions so chat history resets on close/refresh
try {
  localStorage.removeItem('agent_chat_messages');
  localStorage.removeItem('agent_active_job_id');
  localStorage.removeItem('agent_file_previews');
  localStorage.removeItem('agent_files_meta');
  if (typeof window !== 'undefined') {
    const url = new URL(window.location.href);
    if (url.searchParams.has('job')) {
      url.searchParams.delete('job');
      window.history.replaceState(null, '', url.pathname);
    }
  }
} catch (_) {}

const SESSION_KEYS = {
  ACTIVE_JOB_ID: 'agent_session_job_id',
  MESSAGES: 'agent_session_messages',
  FILE_PREVIEWS: 'agent_session_previews',
  FILES_META: 'agent_session_files',
};

// On fresh navigation or manual refresh (F5), clear sessionStorage so history resets.
// Only preserve if the browser discarded the background tab (Chrome Memory Saver).
try {
  const isDiscarded = Boolean(typeof document !== 'undefined' && document.wasDiscarded);
  if (!isDiscarded && typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(SESSION_KEYS.ACTIVE_JOB_ID);
    sessionStorage.removeItem(SESSION_KEYS.MESSAGES);
    sessionStorage.removeItem(SESSION_KEYS.FILE_PREVIEWS);
    sessionStorage.removeItem(SESSION_KEYS.FILES_META);
  }
} catch (_) {}

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('agent_theme') || 'dark';
  });

  const [health, setHealth] = useState(null);

  // Restore only if tab was discarded by browser memory saver in the background
  const [files, setFiles] = useState(() => {
    try {
      if (document.wasDiscarded) {
        const saved = sessionStorage.getItem(SESSION_KEYS.FILES_META);
        if (saved) return JSON.parse(saved);
      }
    } catch (_) {}
    return [];
  });

  const [filePreviews, setFilePreviews] = useState(() => {
    try {
      if (document.wasDiscarded) {
        const saved = sessionStorage.getItem(SESSION_KEYS.FILE_PREVIEWS);
        if (saved) return JSON.parse(saved);
      }
    } catch (_) {}
    return [];
  });

  const [query, setQuery] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [submissionError, setSubmissionError] = useState(null);

  const [activeJobId, setActiveJobId] = useState(() => {
    try {
      if (document.wasDiscarded) {
        return sessionStorage.getItem(SESSION_KEYS.ACTIVE_JOB_ID) || null;
      }
    } catch (_) {}
    return null;
  });

  const [messages, setMessages] = useState(() => {
    try {
      if (document.wasDiscarded) {
        const saved = sessionStorage.getItem(SESSION_KEYS.MESSAGES);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) {
            return parsed.map((m) => ({ ...m, isStreaming: false }));
          }
        }
      }
    } catch (_) {}
    return [];
  });

  const [activeEvidenceId, setActiveEvidenceId] = useState(null);

  const sseCleanupRef = useRef(null);

  // Apply Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('agent_theme', theme);
  }, [theme]);

  // Keep sessionStorage in sync solely for background tab discard recovery
  useEffect(() => {
    try {
      if (messages && messages.length > 0) {
        const serializable = messages.map((m) => ({
          ...m,
          isStreaming: false,
          logs: (m.logs || []).slice(-100),
          files: m.files ? m.files.map((f) => ({ name: f.name, size: f.size || 0, type: f.type || '' })) : null,
          file: m.file ? { name: m.file.name, size: m.file.size || 0, type: m.file.type || '' } : null,
        }));
        sessionStorage.setItem(SESSION_KEYS.MESSAGES, JSON.stringify(serializable));
      } else {
        sessionStorage.removeItem(SESSION_KEYS.MESSAGES);
      }
    } catch (_) {}
  }, [messages]);

  useEffect(() => {
    try {
      if (activeJobId) {
        sessionStorage.setItem(SESSION_KEYS.ACTIVE_JOB_ID, activeJobId);
      } else {
        sessionStorage.removeItem(SESSION_KEYS.ACTIVE_JOB_ID);
      }
    } catch (_) {}
  }, [activeJobId]);

  useEffect(() => {
    try {
      if (filePreviews && filePreviews.length > 0) {
        sessionStorage.setItem(SESSION_KEYS.FILE_PREVIEWS, JSON.stringify(filePreviews));
      } else {
        sessionStorage.removeItem(SESSION_KEYS.FILE_PREVIEWS);
      }
    } catch (_) {}
  }, [filePreviews]);

  useEffect(() => {
    try {
      if (files && files.length > 0) {
        const meta = files.map((f) => ({ name: f.name, size: f.size || 0, type: f.type || '' }));
        sessionStorage.setItem(SESSION_KEYS.FILES_META, JSON.stringify(meta));
      } else {
        sessionStorage.removeItem(SESSION_KEYS.FILES_META);
      }
    } catch (_) {}
  }, [files]);

  // Restore session from server on mount only if tab was discarded by browser
  useEffect(() => {
    const initialJobId = (() => {
      try {
        if (document.wasDiscarded) {
          return sessionStorage.getItem(SESSION_KEYS.ACTIVE_JOB_ID) || null;
        }
      } catch (_) {
        return null;
      }
      return null;
    })();

    if (!initialJobId) return;

    let isMounted = true;
    getJob(initialJobId)
      .then((snapshot) => {
        if (!isMounted || !snapshot) return;

        if (snapshot.status === 'running' || snapshot.status === 'queued') {
          setIsAnalyzing(true);
          setMessages((curr) => {
            const lastMsg = curr[curr.length - 1];
            const targetMsgId = lastMsg && lastMsg.role === 'assistant' ? lastMsg.id : `assistant_${Date.now()}`;
            startStreaming(initialJobId, targetMsgId);
            return curr;
          });
        } else if (snapshot.status === 'finished' || snapshot.status === 'done') {
          setIsAnalyzing(false);

          setMessages((curr) => {
            if (curr.length > 0) {
              return curr.map((m, idx) =>
                idx === curr.length - 1 && m.role === 'assistant'
                  ? {
                      ...m,
                      report: snapshot.report || m.report,
                      artifacts: snapshot.artifacts || m.artifacts,
                      isStreaming: false,
                    }
                  : m
              );
            }
            // Reconstruct if user opened direct URL in a fresh tab
            const userMsg = {
              id: `user_${Date.now() - 1000}`,
              role: 'user',
              text: snapshot.query || 'Analysis of uploaded dataset.',
              files: snapshot.filename ? [{ name: snapshot.filename, size: 0 }] : null,
              file: snapshot.filename ? { name: snapshot.filename, size: 0 } : null,
            };
            const asstMsg = {
              id: `assistant_${Date.now()}`,
              role: 'assistant',
              jobId: initialJobId,
              isStreaming: false,
              report: snapshot.report,
              artifacts: snapshot.artifacts || [],
              logs: [{ type: 'info', text: 'Analysis session successfully restored from server.', t: Date.now() / 1000 }],
              telemetry: { cpu_pct: 0, mem_mb: 0, mem_limit_mb: 1024 },
              sandboxState: 'destroyed',
              containerId: null,
              currentCode: null,
              limitHit: null,
              currentStep: 'report',
              attempt: 1,
            };
            return [userMsg, asstMsg];
          });

          if (snapshot.filename) {
            setFiles((curr) => (curr.length > 0 ? curr : [{ name: snapshot.filename, size: 0 }]));
            setFilePreviews((curr) =>
              curr.length > 0
                ? curr
                : [{ fileName: snapshot.filename, headers: ['Dataset'], rows: [], rowCount: snapshot.rows || 0 }]
            );
          }
        }
      })
      .catch((err) => {
        console.warn('Could not restore job from backend:', err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Initial Health Check
  useEffect(() => {
    fetchHealth().then(setHealth);
    const interval = setInterval(() => {
      fetchHealth().then(setHealth);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) sseCleanupRef.current();
    };
  }, []);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const parsePreviewForFile = (uploadedFile) => {
    return new Promise((resolve) => {
      if (!uploadedFile) return resolve(null);
      if (uploadedFile.name.endsWith('.csv') || uploadedFile.name.endsWith('.tsv')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target.result;
          const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
          if (lines.length > 0) {
            const delimiter = uploadedFile.name.endsWith('.tsv') ? '\t' : ',';
            const headers = lines[0].split(delimiter).map((h) => h.trim().replace(/^"|"$/g, ''));
            const rows = lines.slice(1, 6).map((line) => {
              return line.split(delimiter).map((v) => v.trim().replace(/^"|"$/g, ''));
            });
            resolve({
              fileName: uploadedFile.name,
              headers,
              rows,
              rowCount: lines.length - 1,
            });
          } else {
            resolve({ fileName: uploadedFile.name, headers: ['Data'], rows: [], rowCount: 0 });
          }
        };
        reader.onerror = () => resolve(null);
        reader.readAsText(uploadedFile.slice(0, 10240));
      } else {
        resolve({
          fileName: uploadedFile.name,
          headers: ['Format File'],
          rows: [[uploadedFile.name]],
          rowCount: 1,
        });
      }
    });
  };

  const handleFileSelect = async (selectedFiles, append = false) => {
    if (!selectedFiles) return;
    const incoming = Array.isArray(selectedFiles)
      ? selectedFiles
      : selectedFiles instanceof FileList
      ? Array.from(selectedFiles)
      : [selectedFiles];

    let updatedFiles = [];
    if (append) {
      const existingNames = new Set(files.map((f) => f.name));
      const filtered = incoming.filter((f) => !existingNames.has(f.name));
      updatedFiles = [...files, ...filtered];
    } else {
      updatedFiles = incoming;
    }

    setFiles(updatedFiles);
    setSubmissionError(null);

    const previews = await Promise.all(updatedFiles.map(parsePreviewForFile));
    setFilePreviews(previews.filter(Boolean));
  };

  const handleRemoveFile = (indexToRemove) => {
    const updated = files.filter((_, idx) => idx !== indexToRemove);
    setFiles(updated);
    const updatedPreviews = filePreviews.filter((_, idx) => idx !== indexToRemove);
    setFilePreviews(updatedPreviews);
    if (updated.length === 0) {
      handleResetSession();
    }
  };

  const handleClearFile = () => {
    handleResetSession();
  };

  const handleLoadSample = async (sampleName = 'messy_transactions.csv', append = false) => {
    try {
      const res = await fetch(`/${sampleName}`);
      const blob = await res.blob();
      const sampleFile = new File([blob], sampleName, { type: 'text/csv' });
      await handleFileSelect([sampleFile], append);
    } catch (err) {
      console.error('Failed to load sample file:', err);
    }
  };

  // Unified message sender for initial or follow-up query
  const handleSendMessage = async (userQuery, targetFiles = files) => {
    if (!userQuery.trim() || isAnalyzing) return;
    executeAnalysis(targetFiles || files, userQuery.trim(), activeJobId);
  };

  // Unified analysis executor
  const executeAnalysis = async (targetFiles, userQuery, previousJobId) => {
    setIsAnalyzing(true);
    setSubmissionError(null);

    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `assistant_${Date.now()}`;

    const filesArray = Array.isArray(targetFiles)
      ? targetFiles
      : targetFiles
      ? [targetFiles]
      : files;

    // Determine which files are newly attached in this turn
    let newlyAddedFiles = [];
    if (previousJobId) {
      const priorFileNames = new Set();
      messages.forEach((m) => {
        if (m.files) m.files.forEach((f) => priorFileNames.add(f.name));
        if (m.file) priorFileNames.add(m.file.name);
      });
      newlyAddedFiles = filesArray.filter((f) => !priorFileNames.has(f.name));
    }

    // Add user message
    const userMessage = {
      id: userMsgId,
      role: 'user',
      text: userQuery,
      files: previousJobId
        ? (newlyAddedFiles.length > 0 ? newlyAddedFiles : null)
        : filesArray,
      file: previousJobId
        ? (newlyAddedFiles.length > 0 ? newlyAddedFiles[0] : null)
        : (filesArray[0] || null),
    };

    // Add initial streaming assistant message
    const assistantMessage = {
      id: assistantMsgId,
      role: 'assistant',
      jobId: null,
      isStreaming: true,
      report: null,
      artifacts: [],
      logs: [],
      telemetry: { cpu_pct: 0, mem_mb: 0, mem_limit_mb: 1024 },
      sandboxState: 'created',
      containerId: null,
      currentCode: null,
      limitHit: null,
      currentStep: 'profile',
      attempt: 1,
      suggestedFollowUps: [],
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    try {
      let data;
      if (previousJobId) {
        // Build concise conversation history from completed prior turns
        const historyPayload = messages
          .filter((m) => m.text || (m.report && (m.report.headline || m.report.summary)))
          .map((m) => ({
            role: m.role,
            content:
              m.role === 'user'
                ? m.text
                : (m.report?.headline || m.report?.summary || 'Completed analytical findings and charts.'),
          }));

        // Use follow-up endpoint with any newly added datasets and conversation history
        data = await sendFollowUpMessage(previousJobId, userQuery, newlyAddedFiles, historyPayload);
      } else {
        // Create initial job with all attached files
        data = await createJob(filesArray, userQuery);
      }

      const newJobId = data.job_id;
      setActiveJobId(newJobId);

      // Update assistant message with job ID
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMsgId ? { ...m, jobId: newJobId } : m))
      );

      // Start SSE stream
      startStreaming(newJobId, assistantMsgId);
    } catch (err) {
      setIsAnalyzing(false);
      setSubmissionError(err.message || 'Failed to initiate analysis job.');
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                isStreaming: false,
                report: {
                  title: 'Execution Stopped',
                  headline: err.message || 'A system error occurred.',
                  content_markdown: `> **Notice:** ${err.message || 'Failed to run analysis in sandbox.'}`,
                },
              }
            : m
        )
      );
    }
  };

  // Connect SSE
  const startStreaming = (targetJobId, targetMsgId) => {
    if (sseCleanupRef.current) sseCleanupRef.current();

    const cleanup = subscribeJobEvents(
      targetJobId,
      (event) => {
        handleServerEvent(event, targetJobId, targetMsgId);
      },
      (err) => {
        console.warn('SSE warning:', err);
      }
    );

    sseCleanupRef.current = cleanup;
  };

  const handleServerEvent = (event, currentJobId, targetMsgId) => {
    const { type } = event;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== targetMsgId) return msg;

        switch (type) {
          case 'step_started':
            return {
              ...msg,
              currentStep: event.step,
              logs: [
                ...msg.logs,
                { type: 'info', text: `Step: [${event.step.toUpperCase()}] ${event.title || ''}`, t: event.t },
              ],
            };

          case 'code_generated':
            return {
              ...msg,
              currentCode: event.code,
              logs: [
                ...msg.logs,
                { type: 'info', text: `Python script generated for step ${event.step} (Attempt ${event.attempt}).`, t: event.t },
              ],
            };

          case 'sandbox_created':
            return {
              ...msg,
              containerId: event.container,
              sandboxState: 'created',
              logs: [
                ...msg.logs,
                { type: 'info', text: `Docker container created (CID: ${event.container?.slice(0, 12)}).`, t: event.t },
              ],
            };

          case 'sandbox_started':
            return { ...msg, sandboxState: 'running' };

          case 'stats':
            return {
              ...msg,
              telemetry: {
                cpu_pct: event.cpu_pct || 0,
                mem_mb: event.mem_mb || 0,
                mem_limit_mb: event.mem_limit_mb || 1024,
              },
            };

          case 'stdout':
            return {
              ...msg,
              logs: [...msg.logs, { type: 'stdout', text: event.text, t: event.t }],
            };

          case 'stderr':
            return {
              ...msg,
              logs: [...msg.logs, { type: 'stderr', text: event.text, t: event.t }],
            };

          case 'limit_hit':
            return {
              ...msg,
              limitHit: {
                kind: event.kind,
                message: event.message,
                step: event.step,
                attempt: event.attempt,
              },
              logs: [
                ...msg.logs,
                { type: 'stderr', text: `[CONTAINMENT EVENT] Safe boundary: ${event.kind}. ${event.message}`, t: event.t },
              ],
            };

          case 'sandbox_destroyed':
            return {
              ...msg,
              sandboxState: 'destroyed',
              telemetry: { cpu_pct: 0, mem_mb: 0, mem_limit_mb: 1024 },
              logs: [
                ...msg.logs,
                { type: 'info', text: `Container ${event.container?.slice(0, 12)} safely decommissioned.`, t: event.t },
              ],
            };

          case 'artifact':
            return {
              ...msg,
              artifacts: msg.artifacts.some((a) => a.name === event.name)
                ? msg.artifacts
                : [...msg.artifacts, event],
            };

          case 'report_ready':
            return {
              ...msg,
              report: event.report,
            };

          case 'job_done':
            setIsAnalyzing(false);

            // Re-fetch snapshot to ensure full report markdown and artifacts
            getJob(currentJobId).then((snapshot) => {
              if (snapshot.report) {
                setMessages((curr) =>
                  curr.map((m) =>
                    m.id === targetMsgId
                      ? {
                          ...m,
                          report: snapshot.report,
                          artifacts: snapshot.artifacts || m.artifacts,
                          isStreaming: false,
                        }
                      : m
                  )
                );
              }
            });

            return {
              ...msg,
              isStreaming: false,
              logs: [
                ...msg.logs,
                { type: 'info', text: 'Data analysis completed in sandbox.', t: event.t },
              ],
            };

          case 'job_failed':
            setIsAnalyzing(false);
            return {
              ...msg,
              isStreaming: false,
              logs: [
                ...msg.logs,
                { type: 'stderr', text: `Execution failed: ${event.error}. ${event.detail || ''}`, t: event.t },
              ],
            };

          default:
            return msg;
        }
      })
    );
  };

  const handleResetSession = () => {
    if (sseCleanupRef.current) sseCleanupRef.current();
    setMessages([]);
    setActiveJobId(null);
    setIsAnalyzing(false);
    setSubmissionError(null);
    setFiles([]);
    setFilePreviews([]);
    try {
      sessionStorage.clear();
      localStorage.removeItem('agent_chat_messages');
      localStorage.removeItem('agent_active_job_id');
      localStorage.removeItem('agent_file_previews');
      localStorage.removeItem('agent_files_meta');
      const url = new URL(window.location.href);
      url.searchParams.delete('job');
      window.history.replaceState(null, '', url.pathname);
    } catch (_) {}
  };

  return (
    <div className="app-shell">
      <Header
        health={health}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onLoadSample={handleLoadSample}
        isAnalyzing={isAnalyzing}
      />

      <main className="main-content">
        <div className="conversational-analyst-view">
          {/* Top Minimal Dataset Context Bar (Visible only when chat has messages) */}
          {messages.length > 0 && (
            <div className="dataset-context-bar">
              <div className="dataset-context-left">
                <FileSpreadsheet size={16} className="text-accent icon-mr" />
                {files.length > 1 ? (
                  <div className="dataset-multi-chip-list">
                    <span className="dataset-compare-badge font-mono">Comparison Mode ({files.length} Datasets)</span>
                    {files.map((f, idx) => (
                      <span key={idx} className="dataset-chip-item font-mono">
                        {f.name}
                        {filePreviews[idx]?.rowCount ? ` (${filePreviews[idx].rowCount} rows)` : ''}
                      </span>
                    ))}
                  </div>
                ) : (
                  <>
                    <span className="dataset-name font-mono">{files[0]?.name || 'Dataset'}</span>
                    {filePreviews[0]?.rowCount && (
                      <span className="dataset-rows-tag font-mono">
                        {filePreviews[0].rowCount} rows
                      </span>
                    )}
                  </>
                )}
                {activeJobId && (
                  <span className="dataset-job-tag font-mono">ID: {activeJobId}</span>
                )}
              </div>
              <button
                type="button"
                onClick={handleResetSession}
                className="btn-secondary btn-sm"
                disabled={isAnalyzing}
              >
                Switch Dataset / New Analysis
              </button>
            </div>
          )}

          {/* Unified Single-Page Conversational Analyst Workspace */}
          <ChatWorkspace
            files={files}
            file={files[0] || null}
            filePreviews={filePreviews}
            filePreview={filePreviews[0] || null}
            onFileSelect={handleFileSelect}
            onRemoveFile={handleRemoveFile}
            onClearFile={handleClearFile}
            onLoadSample={handleLoadSample}
            messages={messages}
            onSendMessage={handleSendMessage}
            isAnalyzing={isAnalyzing}
            onSelectEvidence={(eid) => setActiveEvidenceId(eid)}
            onResetSession={handleResetSession}
          />
        </div>

        {/* Global Error Toast */}
        {submissionError && (
          <div className="error-banner" role="alert">
            <span>{submissionError}</span>
          </div>
        )}

        {/* Evidence Verification Drawer */}
        {activeEvidenceId && (
          <EvidenceDrawer
            jobId={activeJobId}
            evidenceId={activeEvidenceId}
            onClose={() => setActiveEvidenceId(null)}
          />
        )}
      </main>
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Send,
  Terminal,
  Cpu,
  HardDrive,
  ShieldCheck,
  ShieldAlert,
  Download,
  Maximize2,
  FileSpreadsheet,
  Code,
  Sparkles,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Loader2,
  X,
  Copy,
  Check,
  Upload,
  Play,
  AlertCircle,
  Plus,
  Clock,
  ChevronUp,
  Database,
  Trash2,
} from 'lucide-react';
import { getFileUrl } from '../api';

const STARTER_PROMPTS = [
  {
    icon: Sparkles,
    label: 'Comprehensive Analysis',
    desc: 'Clean data inconsistencies, identify top spending/growth drivers, and visualize key metric distributions.',
    prompt: 'Perform a comprehensive analysis on this dataset: clean data inconsistencies, identify key drivers, detect anomaly values, and visualize key metric distributions.',
  },
  {
    icon: AlertCircle,
    label: 'Anomaly & Quality Audit',
    desc: 'Audit irregular date formats, vendor naming variations, and potential duplicate records.',
    prompt: 'Audit the data quality of this dataset. Identify irregular values, inconsistent date and currency formats, and detect duplicate rows that could cause double-spending.',
  },
  {
    icon: Code,
    label: 'Self-Healing Data Cleaning',
    desc: 'Standardize dates to ISO YYYY-MM-DD, parse currency to numeric float, and export clean.csv.',
    prompt: 'Clean this dataset using the self-healing cleaner: standardize date formats to ISO YYYY-MM-DD, clean currency values into numeric floats, remove duplicate rows, and export as clean.csv.',
  },
  {
    icon: ShieldCheck,
    label: 'Sandbox Resilience Test',
    desc: 'Simulate containment boundary execution to verify Blast Radius Zero isolation.',
    prompt: 'Run a stress-test on the sandbox: execute intensive computation and verify that timeout and 512MB memory limits safely contain execution without host exposure.',
  },
];

const COMPARISON_STARTER_PROMPTS = [
  {
    icon: Sparkles,
    label: 'Compare All Datasets',
    desc: 'Compare transaction metrics, totals, averages, and categorical patterns across files.',
    prompt: 'Compare all uploaded datasets comprehensively: compute row volume differences, total amounts, average values, and identify pattern similarities or divergences.',
  },
  {
    icon: AlertCircle,
    label: 'Variance & Reconciliation Analysis',
    desc: 'Identify data discrepancies, out-of-sync rows, or cross-file anomalies.',
    prompt: 'Perform a cross-dataset reconciliation audit: detect records present in one file but absent in another, and identify value discrepancies that require adjustment.',
  },
  {
    icon: Code,
    label: 'Side-by-Side Visual Comparison',
    desc: 'Generate comparative bar charts to evaluate key metrics across datasets.',
    prompt: 'Generate a side-by-side comparative bar chart between the uploaded datasets comparing total volume or expenditure per category.',
  },
  {
    icon: ShieldCheck,
    label: 'Multi-File Sandbox Containment Test',
    desc: 'Verify secure comparative processing with zero network egress and 512MB RAM limit.',
    prompt: 'Run a multi-dataset comparative analysis within the isolated sandbox and verify zero external network egress and strict timeout containment.',
  },
];

export function ChatWorkspace({
  files = [],
  file,
  filePreviews = [],
  filePreview,
  onFileSelect,
  onRemoveFile,
  onClearFile,
  onLoadSample,
  messages, // array of { id, role: 'user' | 'assistant', text, report, artifacts, logs, telemetry, sandboxState, containerId, currentCode, limitHit, isStreaming, currentStep, attempt }
  onSendMessage,
  isAnalyzing,
  onSelectEvidence,
  onResetSession,
}) {
  const activeFiles = files && files.length > 0 ? files : (file ? [file] : []);
  const activePreviews = filePreviews && filePreviews.length > 0 ? filePreviews : (filePreview ? [filePreview] : []);

  const [inputQuery, setInputQuery] = useState('');
  const [activeModalChart, setActiveModalChart] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showDatasetNotice, setShowDatasetNotice] = useState(false);
  const [showDatasetPopover, setShowDatasetPopover] = useState(false);
  const [previewTabIdx, setPreviewTabIdx] = useState(0);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const popoverRef = useRef(null);

  // Close dataset popover on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setShowDatasetPopover(false);
      }
    }
    if (showDatasetPopover) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDatasetPopover]);

  // Auto scroll to bottom when new messages or logs arrive
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!inputQuery.trim() || isAnalyzing) return;
    if (activeFiles.length === 0) {
      setShowDatasetNotice(true);
      setTimeout(() => setShowDatasetNotice(false), 4500);
      return;
    }
    onSendMessage(inputQuery.trim(), activeFiles);
    setInputQuery('');
    setShowDatasetNotice(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleTextareaInput = (e) => {
    setInputQuery(e.target.value);
    if (showDatasetNotice) setShowDatasetNotice(false);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files, true);
      setShowDatasetNotice(false);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files, true);
      setShowDatasetNotice(false);
      e.target.value = '';
    }
  };

  const handleSelectStarter = (promptText) => {
    setInputQuery(promptText);
    if (activeFiles.length === 0) {
      setShowDatasetNotice(true);
    }
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="chat-workspace-container">
      {/* Hidden File Input for Attachment (Supports multiple files) */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileInputChange}
        accept=".csv,.tsv,.xlsx,.xls,.json"
        multiple
        className="hidden-input"
      />

      {/* Main Messages or Empty-State Launchpad */}
      {messages.length === 0 ? (
        <div className="welcome-launchpad">
          {/* 1. Hero Title & 1-Sentence Pitch (ChatGPT style) */}
          <div className="welcome-hero">
            <div className="welcome-badge-strip">
              <span className="welcome-badge font-mono">
                <span className="live-pulse-dot" />
                Vultr Agent Rush &bull; Track 01: Blast Radius Zero
              </span>
            </div>
            <h2 className="welcome-title">Ready to Analyze Your Data</h2>
            <p className="welcome-subtitle">
              Autonomous multi-agent analytical system with isolated Docker sandboxing. Upload one or more datasets for self-healing cleaning, cross-file comparative analysis, anomaly auditing, and verified visualizations with zero data-leakage risk.
            </p>
          </div>

          {/* 2. Mandatory Dataset Import / Connected Box */}
          <div className="launchpad-dataset-section">
            <div className="dataset-section-header">
              <div className="header-left">
                <FileSpreadsheet size={16} className="text-accent" />
                <span className="section-title">
                  {activeFiles.length > 1
                    ? `Connected Datasets (${activeFiles.length} Comparison Files)`
                    : 'Select or Upload Datasets'}
                </span>
                <span className="badge-required font-mono">
                  {activeFiles.length > 1 ? 'Multi-File' : 'Required'}
                </span>
              </div>
            </div>

            {activeFiles.length === 0 ? (
              <div
                className={`launchpad-dropzone ${isDragging ? 'dropzone-active' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
              >
                <div className="dropzone-icon-box">
                  <Upload size={22} />
                </div>
                <p className="dropzone-text-primary">
                  Drag & drop 1 or more dataset files here, or <span className="text-highlight">browse files</span>
                </p>
                <p className="dropzone-text-secondary font-mono">
                  Supports multi-file .csv, .tsv, .xlsx, .json for comparison (Max 100MB per file)
                </p>
              </div>
            ) : (
              <div className="launchpad-file-connected">
                <div className="connected-header">
                  <div className="connected-meta">
                    <div className="connected-icon-box">
                      <FileSpreadsheet size={20} className="text-success" />
                    </div>
                    <div>
                      <div className="connected-name-row">
                        <span className="connected-filename font-mono">
                          {activeFiles.length > 1
                            ? `${activeFiles.length} Connected Datasets for Comparison`
                            : activeFiles[0]?.name}
                        </span>
                        <span className="connected-status-badge font-mono">
                          <Check size={12} className="icon-mr" /> Connected
                        </span>
                      </div>
                      <p className="connected-subtext font-mono">
                        {activeFiles.length > 1
                          ? `Total ${activeFiles.length} files ready for sandbox analysis and comparison`
                          : `${(activeFiles[0]?.size / 1024).toFixed(1)} KB • ${
                              activePreviews[0]
                                ? `${activePreviews[0].rowCount} rows detected`
                                : 'Ready for sandbox analysis'
                            }`}
                      </p>
                    </div>
                  </div>
                  <div className="connected-actions-row">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-secondary btn-sm"
                      title="Add another file for comparison"
                      disabled={isAnalyzing}
                    >
                      <Plus size={14} className="icon-mr" />
                      Add File
                    </button>
                    <button
                      type="button"
                      onClick={onClearFile}
                      className="btn-secondary btn-sm"
                      title="Clear all files"
                      disabled={isAnalyzing}
                    >
                      <X size={14} className="icon-mr" />
                      Clear All
                    </button>
                  </div>
                </div>

                {/* List of Connected Files */}
                <div className="connected-files-badges-list">
                  {activeFiles.map((f, fIdx) => (
                    <div key={fIdx} className="connected-file-pill font-mono">
                      <FileSpreadsheet size={13} className="text-accent" />
                      <span className="pill-fname">{f.name}</span>
                      <span className="pill-fsize">({(f.size / 1024).toFixed(1)} KB)</span>
                      {activePreviews[fIdx]?.rowCount ? (
                        <span className="pill-frows">{activePreviews[fIdx].rowCount} rows</span>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => onRemoveFile ? onRemoveFile(fIdx) : onClearFile()}
                        className="btn-pill-remove"
                        title={`Remove ${f.name}`}
                        disabled={isAnalyzing}
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Client-side Table Preview Tabs */}
                {activePreviews.length > 0 && (
                  <div className="launchpad-preview-table-box">
                    <div className="preview-table-tabs font-mono">
                      <span className="preview-table-label">Data Preview:</span>
                      {activePreviews.map((p, pIdx) => (
                        <button
                          key={pIdx}
                          type="button"
                          className={`preview-tab-btn ${previewTabIdx === pIdx ? 'tab-active' : ''}`}
                          onClick={() => setPreviewTabIdx(pIdx)}
                        >
                          {p.fileName || `File ${pIdx + 1}`}
                          {p.rowCount ? ` (${p.rowCount} rows)` : ''}
                        </button>
                      ))}
                    </div>

                    {activePreviews[previewTabIdx] && activePreviews[previewTabIdx].headers && (
                      <div className="preview-table-scroll">
                        <table className="preview-table font-mono">
                          <thead>
                            <tr>
                              {activePreviews[previewTabIdx].headers.map((h, i) => (
                                <th key={i}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {activePreviews[previewTabIdx].rows.slice(0, 3).map((row, rIdx) => (
                              <tr key={rIdx}>
                                {row.map((val, cIdx) => (
                                  <td key={cIdx}>{val}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 3. Starter Prompt Cards (ChatGPT style cards) */}
          <div className="launchpad-starters-section">
            <div className="starters-header">
              <span className="starters-label">
                {activeFiles.length >= 2
                  ? 'Choose a Comparison Direction or Type Below:'
                  : 'Choose an Analysis Direction or Type Below:'}
              </span>
              {activeFiles.length === 1 && (
                <span className="starters-tip font-mono">
                  Tip: Upload a second file to activate comparative analysis!
                </span>
              )}
            </div>
            <div className="starters-grid">
              {(activeFiles.length >= 2 ? COMPARISON_STARTER_PROMPTS : STARTER_PROMPTS).map((item, idx) => {
                const Icon = item.icon;
                return (
                  <div
                    key={idx}
                    className="starter-card"
                    onClick={() => handleSelectStarter(item.prompt)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="starter-card-top">
                      <div className="starter-icon-box">
                        <Icon size={16} />
                      </div>
                      <span className="starter-card-title">{item.label}</span>
                    </div>
                    <p className="starter-card-desc">{item.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>


        </div>
      ) : (
        /* Messages Scroll Area */
        <div className="chat-messages-flow">
          {messages.map((msg, index) => (
            <div
              key={msg.id || index}
              className={`chat-row chat-row-${msg.role}`}
            >
              {msg.role === 'user' ? (
                <div className="user-message-bubble">
                  <p className="user-message-text">{msg.text}</p>
                  {msg.files && msg.files.length > 0 ? (
                    <div className="user-message-files-row">
                      {msg.files.map((f, fIdx) => (
                        <div key={fIdx} className="user-message-file-badge font-mono">
                          <FileSpreadsheet size={13} className="icon-mr text-accent" />
                          <span>{f.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : msg.file ? (
                    <div className="user-message-file-badge font-mono">
                      <FileSpreadsheet size={13} className="icon-mr text-accent" />
                      <span>{msg.file.name}</span>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="analyst-response-card">
                  {/* 1. Real-time Sandbox Lifecycle Badge / Accordion */}
                  <SandboxStatusWidget
                    msg={msg}
                    onSelectEvidence={onSelectEvidence}
                  />

                  {/* 2. Rich Markdown Analysis Document */}
                  <div className="analyst-markdown-body">
                    {msg.report && (
                      <MarkdownReportRenderer
                        jobId={msg.jobId}
                        report={msg.report}
                        artifacts={msg.artifacts || []}
                        onSelectEvidence={onSelectEvidence}
                        onZoomChart={(chart) => setActiveModalChart(chart)}
                      />
                    )}
                  </div>

                  {/* 3. Generated Artifacts Download Bar (Clean CSV & Charts) */}
                  {msg.artifacts && msg.artifacts.length > 0 && (
                    <div className="artifacts-action-bar">
                      <span className="artifacts-bar-title font-mono">
                        <Sparkles size={14} className="icon-mr text-accent" />
                        Generated Artifacts & Exports:
                      </span>
                      <div className="artifacts-pills-row">
                        {msg.artifacts.map((art, aIdx) => {
                          const fileUrl = getFileUrl(msg.jobId, art.name);
                          const isCsv = art.name.endsWith('.csv');
                          return (
                            <a
                              key={aIdx}
                              href={fileUrl}
                              download={art.name}
                              className={`artifact-download-pill ${
                                isCsv ? 'pill-csv' : 'pill-chart'
                              }`}
                              title={`Download ${art.name}`}
                            >
                              <Download size={13} className="icon-mr" />
                              <span>{art.name}</span>
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  )}


                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Bottom Sticky Input Bar (Unified & Always Present) */}
      <div className="chat-input-sticky-bar">
        {/* Warning Toast if User clicks send without attaching a dataset */}
        {showDatasetNotice && (
          <div className="input-warning-toast" role="alert">
            <AlertCircle size={15} className="text-accent" />
            <span>A dataset is required for analysis! Please upload or select a file first.</span>
          </div>
        )}

        <div className="chat-input-wrapper" ref={popoverRef}>
          {/* Active Dataset Popover Dropdown Menu */}
          {showDatasetPopover && activeFiles.length > 0 && (
            <div className="dataset-popover-menu" role="dialog" aria-label="Attached datasets">
              <div className="dataset-popover-header">
                <div className="dataset-popover-title">
                  <Database size={14} className="text-accent" />
                  <span>Attached Datasets ({activeFiles.length})</span>
                </div>
                <div className="dataset-popover-actions">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-popover-add font-mono"
                    title="Add another dataset file"
                    disabled={isAnalyzing}
                  >
                    <Plus size={12} />
                    <span>Add File</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDatasetPopover(false)}
                    className="btn-popover-close"
                    title="Close"
                  >
                    <X size={13} />
                  </button>
                </div>
              </div>

              <div className="dataset-popover-list custom-scrollbar">
                {activeFiles.map((f, idx) => {
                  const preview = activePreviews[idx];
                  return (
                    <div key={idx} className="dataset-popover-item">
                      <div className="dataset-popover-file-icon">
                        <FileSpreadsheet size={15} />
                      </div>
                      <div className="dataset-popover-file-info">
                        <span className="dataset-popover-filename" title={f.name}>
                          {f.name}
                        </span>
                        <span className="dataset-popover-file-meta font-mono">
                          {preview?.rowCount ? `${preview.rowCount.toLocaleString()} rows` : ''}
                          {f.size ? ` • ${(f.size / 1024).toFixed(1)} KB` : ''}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (onRemoveFile) onRemoveFile(idx);
                          else onClearFile();
                          if (activeFiles.length <= 1) setShowDatasetPopover(false);
                        }}
                        className="btn-popover-remove-item"
                        title={`Remove ${f.name}`}
                        disabled={isAnalyzing}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  );
                })}
              </div>

              <div className="dataset-popover-footer">
                <span className="footer-note">Docker sandbox read-only mount</span>
                {activeFiles.length > 1 && (
                  <button
                    type="button"
                    onClick={() => {
                      onClearFile();
                      setShowDatasetPopover(false);
                    }}
                    className="btn-popover-clear-all font-mono"
                    disabled={isAnalyzing}
                  >
                    Clear All
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Left Controls: Upload Button + Compact Dataset Badge */}
          <div className="chat-input-left-controls">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className={`btn-attach-dataset ${activeFiles.length === 0 ? 'pulse-prompt' : ''}`}
              title={activeFiles.length > 0 ? 'Upload another dataset' : 'Upload dataset (.csv, .xlsx, .json)'}
              disabled={isAnalyzing}
            >
              <Upload size={16} />
            </button>

            {activeFiles.length > 0 && (
              <button
                type="button"
                onClick={() => setShowDatasetPopover((prev) => !prev)}
                className={`btn-dataset-badge ${showDatasetPopover ? 'active' : ''}`}
                title="Click to view and manage attached datasets"
              >
                <FileSpreadsheet size={13} className="text-accent flex-shrink-0" />
                <span className="badge-name font-mono">
                  {activeFiles.length === 1 ? activeFiles[0].name : `${activeFiles.length} Datasets`}
                </span>
                <ChevronUp size={12} className={`badge-chevron ${showDatasetPopover ? 'rotated' : ''}`} />
              </button>
            )}
          </div>

          <textarea
            ref={textareaRef}
            value={inputQuery}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            placeholder={
              isAnalyzing
                ? 'Analysis executing in isolated Docker sandbox...'
                : activeFiles.length > 1
                ? `Type analysis or comparison instructions for these ${activeFiles.length} datasets (e.g. "Compare sales variance and category distribution across both files")...`
                : activeFiles.length === 1
                ? 'Type analysis instructions for this dataset (e.g. "Analyze transaction anomalies and visualize category breakdown")...'
                : 'Upload a CSV/Excel file or ask a question to begin...'
            }
            rows={1}
            disabled={isAnalyzing}
            className="chat-textarea"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!inputQuery.trim() || isAnalyzing}
            className="btn-send-message"
            aria-label="Send analysis query"
          >
            {isAnalyzing ? (
              <Loader2 size={16} className="spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>
      </div>

      {/* Image Zoom Modal */}
      {activeModalChart && (
        <div
          className="modal-backdrop"
          onClick={() => setActiveModalChart(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title font-mono">{activeModalChart.name}</span>
              <div className="modal-actions">
                <a
                  href={getFileUrl(activeModalChart.jobId, activeModalChart.name)}
                  download={activeModalChart.name}
                  className="btn-secondary btn-sm"
                >
                  <Download size={14} className="icon-mr" />
                  Download PNG
                </a>
                <button
                  type="button"
                  onClick={() => setActiveModalChart(null)}
                  className="btn-icon"
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="modal-body">
              <img
                src={getFileUrl(activeModalChart.jobId, activeModalChart.name)}
                alt={activeModalChart.name}
                className="modal-img"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Live Sandbox Status Widget & Mini-Terminal showing live telemetry, human status & auto-scrolling terminal logs
 */
function SandboxStatusWidget({ msg, onSelectEvidence }) {
  const [expanded, setExpanded] = useState(false);
  const [showInlineLogs, setShowInlineLogs] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState('logs'); // 'logs' | 'code'
  const [copied, setCopied] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const terminalEndRef = useRef(null);
  const modalTerminalEndRef = useRef(null);

  const isRunning = msg.isStreaming || msg.sandboxState === 'running';
  const hasReport = Boolean(msg.report);
  const memUsed = msg.telemetry?.mem_mb || 0;
  const memLimit = msg.telemetry?.mem_limit_mb || 1024;
  const cpuPct = Math.round(msg.telemetry?.cpu_pct || 0);

  // Live timer counting execution seconds
  useEffect(() => {
    let timer;
    if (isRunning) {
      timer = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isRunning]);

  // Auto-scroll inline terminal viewport to bottom when logs arrive if toggled open
  useEffect(() => {
    if (showInlineLogs) {
      terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [msg.logs, showInlineLogs]);

  // Auto-scroll modal terminal if open
  useEffect(() => {
    if (isModalOpen && modalTab === 'logs') {
      modalTerminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [msg.logs, isModalOpen, modalTab]);

  const handleCopyLogs = (e) => {
    e.stopPropagation();
    const text = (msg.logs || []).map((l) => `[${l.type}] ${l.text}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyCode = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(msg.currentCode || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getHumanStep = (step) => {
    switch (step) {
      case 'profile':
        return 'Profiling dataset structure, missing values, column types, and data health...';
      case 'plan':
        return 'Formulating analytical strategy and visualization blueprint...';
      case 'clean':
        return 'Executing self-healing data wrangling and format standardization...';
      case 'eda':
        return 'Analyzing correlations and rendering visual charts...';
      case 'reporter':
      case 'advisor':
        return 'Synthesizing analytical findings and compiling verified executive report...';
      default:
        return 'Executing analysis in isolated Docker sandbox (Blast Radius Zero)...';
    }
  };

  const getStepBadge = (step) => {
    switch (step) {
      case 'profile':
        return 'PROFILING';
      case 'clean':
        return 'CLEANING';
      case 'eda':
        return 'EDA & CHARTS';
      case 'report':
      case 'reporter':
        return 'REPORTING';
      case 'advisor':
        return 'ADVISORY';
      case 'plan':
        return 'PLANNING';
      default:
        return (step || 'SANDBOX').toUpperCase();
    }
  };

  // Extract the latest dynamic real-time progress text from the log stream
  const getDynamicStatus = () => {
    const logs = msg.logs || [];
    for (let i = logs.length - 1; i >= 0; i--) {
      const l = logs[i];
      const text = (l.text || '').trim();
      // Skip brackets and raw JSON data dumps
      if (!text || text === '{' || text === '}' || text.startsWith('{"') || text.startsWith('[{')) continue;

      if (l.type === 'info') {
        if (text.startsWith('Tahap: [') || text.startsWith('Step: [')) {
          const match = text.match(/(?:Tahap|Step):\s*\[(\w+)\]\s*(.*)/i);
          if (match) {
            return `Step ${match[1].toUpperCase()}: ${match[2] || getHumanStep(match[1].toLowerCase())}`;
          }
        }
        return text;
      }
      if (l.type === 'stdout' && text.length > 3 && !text.startsWith('{"')) {
        return text.replace(/^>\s*/, '');
      }
    }
    return getHumanStep(msg.currentStep);
  };

  // When running OR if not yet finished (no report), display Live Status Bar.
  // When finished with report, auto-collapse into sleek Summary Pill to prioritize Report & Charts.
  const showLiveTerminal = isRunning || !hasReport;
  const currentDynamicText = getDynamicStatus();

  return (
    <div className="sandbox-widget-container">
      {/* 1. RUNNING STATE: 1-Line Sleek Animated Status Bar */}
      {showLiveTerminal ? (
        <div className="live-status-bar-card">
          <div className="live-status-bar-main">
            <div className="status-bar-left">
              {/* Radar Orbit Loader with glow */}
              <div className="status-radar-spinner" title="Docker Sandbox Running">
                <span className="radar-core" />
                <span className="radar-ring" />
              </div>

              {/* Step Pill */}
              <span className="status-step-pill font-mono">
                {getStepBadge(msg.currentStep)}
              </span>

              {/* Dynamic Real-Time Animated Text */}
              <div className="status-message-wrapper" title={currentDynamicText}>
                <span key={currentDynamicText} className="status-dynamic-text">
                  {currentDynamicText}
                </span>
              </div>
            </div>

            <div className="status-bar-right">
              {/* Live Elapsed Timer */}
              <span className="status-timer-chip font-mono" title="Elapsed Execution Time">
                <Clock size={11} className="icon-mr text-accent" />
                {elapsedSeconds}s
              </span>

              {/* RAM Telemetry Chip */}
              {memUsed > 0 && (
                <span className="status-ram-chip font-mono" title="Sandbox RAM Usage">
                  <HardDrive size={11} className="icon-mr" />
                  {memUsed} MB
                </span>
              )}

              {/* Toggle Inline Terminal Button */}
              <button
                type="button"
                className={`btn-toggle-terminal ${showInlineLogs ? 'active' : ''}`}
                onClick={() => setShowInlineLogs(!showInlineLogs)}
                title={showInlineLogs ? 'Close Terminal Logs' : 'Open Real-Time Terminal Logs'}
              >
                <Terminal size={12} className="icon-mr" />
                <span className="font-mono">Logs ({(msg.logs || []).length})</span>
                {showInlineLogs ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </button>

              {/* Maximize to Modal Button */}
              <button
                type="button"
                className="btn-terminal-maximize-mini"
                onClick={() => setIsModalOpen(true)}
                title="Open Fullscreen Inspector"
              >
                <Maximize2 size={12} />
              </button>
            </div>
          </div>

          {/* Glowing Laser Progress Line */}
          <div className="status-laser-progress" />

          {/* Inline Monospace Terminal Viewport (Expandable when user clicks 'Log') */}
          {showInlineLogs && (
            <div className="inline-live-terminal font-mono">
              <div className="inline-live-terminal-viewport">
                {(msg.logs || []).length === 0 ? (
                  <div className="terminal-line line-info">
                    <span className="log-prefix">[SYS]</span>
                    <span className="log-text">Initializing Docker container isolation (Blast Radius Zero)...</span>
                  </div>
                ) : (
                  msg.logs.map((l, lIdx) => (
                    <div key={lIdx} className={`terminal-line line-${l.type}`}>
                      <span className="log-prefix">
                        {l.type === 'stderr' ? '[ERR]' : l.type === 'info' ? '[SYS]' : '>'}
                      </span>
                      <span className="log-text">{l.text}</span>
                    </div>
                  ))
                )}
                <div className="terminal-cursor-line">
                  <span className="log-prefix">&gt;</span>
                  <span className="terminal-cursor">▍</span>
                </div>
                <div ref={terminalEndRef} />
              </div>
            </div>
          )}
        </div>
      ) : (
        /* 2. COMPLETED STATE: Sleek Auto-Collapsed Summary Pill */
        <div
          className="sandbox-widget-pill widget-done"
          onClick={() => setExpanded(!expanded)}
          role="button"
          tabIndex={0}
        >
          <div className="widget-left-group">
            <ShieldCheck size={16} className="text-success" />
            <span className="widget-title font-mono">
              Secure Execution in Docker Sandbox (Blast Radius Zero)
            </span>
            {msg.containerId && (
              <span className="widget-cid font-mono">
                CID: {msg.containerId.slice(0, 10)}
              </span>
            )}
          </div>

          <div className="widget-right-group">
            <span className="widget-telemetry-tag font-mono">
              <HardDrive size={12} className="icon-mr" />
              Peak {memUsed} MB
            </span>
            <button
              type="button"
              className="btn-terminal-view-logs"
              onClick={(e) => {
                e.stopPropagation();
                setIsModalOpen(true);
              }}
              title="View terminal history and Python script"
            >
              <Terminal size={12} className="icon-mr text-accent" />
              <span>Terminal Logs ({msg.logs?.length || 0})</span>
              <Maximize2 size={11} className="icon-ml" />
            </button>
            <span className="widget-toggle-icon" title="Toggle inline summary">
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          </div>
        </div>
      )}

      {/* Containment Moment Banner if limit hit */}
      {msg.limitHit && (
        <div className="containment-alert-card" role="alert">
          <ShieldAlert size={18} className="containment-icon text-danger" />
          <div className="containment-text">
            <strong>Safe Boundary Triggered ({msg.limitHit.kind}):</strong> Sandbox safely neutralized
            execution ({msg.limitHit.message || 'Limit exceeded'}) with zero host exposure.
          </div>
        </div>
      )}

      {/* Inline Expanded Content (for completed state if user expands inline) */}
      {!showLiveTerminal && expanded && (
        <div className="sandbox-expanded-content">
          {msg.currentCode && (
            <div className="expanded-code-box">
              <div className="box-topbar font-mono">
                <div className="box-topbar-left">
                  <Code size={13} className="icon-mr text-accent" />
                  <span>Executed Python Script:</span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyCode}
                  className="btn-copy-code"
                  title="Copy script"
                >
                  {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy Script'}</span>
                </button>
              </div>
              <pre className="box-pre font-mono">
                <code>{msg.currentCode}</code>
              </pre>
            </div>
          )}

          <div className="expanded-terminal-box">
            <div className="box-topbar font-mono">
              <div className="box-topbar-left">
                <Terminal size={13} className="icon-mr text-accent" />
                <span>Sandbox Terminal Logs (stdout / stderr):</span>
              </div>
              <div className="box-topbar-right">
                <button
                  type="button"
                  onClick={handleCopyLogs}
                  className="btn-copy-code"
                  title="Copy logs"
                >
                  {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy Logs'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(true)}
                  className="btn-copy-code"
                  title="Maximize modal"
                >
                  <Maximize2 size={12} className="icon-mr" />
                  <span>Maximize</span>
                </button>
              </div>
            </div>
            <div className="terminal-log-content font-mono">
              {(msg.logs || []).length === 0 ? (
                <div className="terminal-empty">No terminal output yet...</div>
              ) : (
                msg.logs.map((l, lIdx) => (
                  <div key={lIdx} className={`terminal-line line-${l.type}`}>
                    <span className="log-prefix">
                      {l.type === 'stderr' ? '[ERR]' : l.type === 'info' ? '[SYS]' : '>'}
                    </span>
                    <span className="log-text">{l.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 3. FULLSCREEN / MAXIMIZED INSPECTOR MODAL */}
      {isModalOpen && (
        <div
          className="sandbox-modal-backdrop"
          onClick={() => setIsModalOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="sandbox-modal-card"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="sandbox-modal-header">
              <div className="modal-header-left">
                <Terminal size={16} className="text-accent" />
                <span className="modal-title font-mono">Sandbox Inspector</span>
                {msg.containerId && (
                  <span className="modal-cid-badge font-mono">
                    CID: {msg.containerId.slice(0, 12)}
                  </span>
                )}
                {isRunning && (
                  <span className="modal-live-tag font-mono">
                    <span className="live-pulse-dot" /> LIVE
                  </span>
                )}
              </div>

              {/* Tabs Switcher */}
              <div className="sandbox-modal-tabs font-mono">
                <button
                  type="button"
                  className={`modal-tab-btn ${modalTab === 'logs' ? 'tab-active' : ''}`}
                  onClick={() => setModalTab('logs')}
                >
                  <Terminal size={13} className="icon-mr" />
                  Terminal Logs ({msg.logs?.length || 0})
                </button>
                {msg.currentCode && (
                  <button
                    type="button"
                    className={`modal-tab-btn ${modalTab === 'code' ? 'tab-active' : ''}`}
                    onClick={() => setModalTab('code')}
                  >
                    <Code size={13} className="icon-mr" />
                    Python Script
                  </button>
                )}
              </div>

              {/* Actions */}
              <div className="modal-header-right">
                <button
                  type="button"
                  onClick={modalTab === 'logs' ? handleCopyLogs : handleCopyCode}
                  className="btn-modal-action"
                  title="Copy content"
                >
                  {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
                  <span>{copied ? 'Copied' : modalTab === 'logs' ? 'Copy Logs' : 'Copy Code'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="btn-modal-close"
                  aria-label="Close modal"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="sandbox-modal-body">
              {modalTab === 'logs' ? (
                <div className="modal-terminal-scroll font-mono">
                  {(msg.logs || []).length === 0 ? (
                    <div className="terminal-empty">No terminal output yet...</div>
                  ) : (
                    msg.logs.map((l, lIdx) => (
                      <div key={lIdx} className={`terminal-line line-${l.type}`}>
                        <span className="log-line-num">{lIdx + 1}</span>
                        <span className="log-prefix">
                          {l.type === 'stderr' ? '[ERR]' : l.type === 'info' ? '[SYS]' : '>'}
                        </span>
                        <span className="log-text">{l.text}</span>
                      </div>
                    ))
                  )}
                  {isRunning && (
                    <div className="terminal-cursor-line">
                      <span className="log-line-num">{(msg.logs?.length || 0) + 1}</span>
                      <span className="log-prefix">&gt;</span>
                      <span className="terminal-cursor">▍</span>
                    </div>
                  )}
                  <div ref={modalTerminalEndRef} />
                </div>
              ) : (
                <div className="modal-code-scroll font-mono">
                  <pre className="modal-code-pre">
                    <code>{msg.currentCode}</code>
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="sandbox-modal-footer font-mono">
              <span>Status: {msg.sandboxState || 'unknown'}</span>
              <span>Memory: {memUsed} MB / {memLimit} MB</span>
              <span>CPU: {cpuPct}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Custom Markdown Report Renderer with inline chart cards and interactive citation pills
 */
function MarkdownReportRenderer({
  jobId,
  report,
  artifacts,
  onSelectEvidence,
  onZoomChart,
}) {
  const chartArtifacts = (artifacts || []).filter((a) => a.name.endsWith('.png'));

  // Determine if content_markdown has rich markdown or advisor guidance
  const rawMarkdown = (report.content_markdown || '').trim();
  const hasRichMarkdown = rawMarkdown.length > 20 && (rawMarkdown.includes('#') || rawMarkdown.includes('\n') || rawMarkdown.includes('>'));
  const isWarningReport = Boolean(
    report.title?.toLowerCase().includes('warning') ||
    report.title?.toLowerCase().includes('mismatch') ||
    report.title?.toLowerCase().includes('notice') ||
    report.title?.toLowerCase().includes('peringatan') ||
    report.title?.toLowerCase().includes('tidak sesuai') ||
    report.title?.toLowerCase().includes('pemberitahuan') ||
    report.headline?.toLowerCase().includes('not found') ||
    report.headline?.toLowerCase().includes('tidak ditemukan') ||
    report.headline?.toLowerCase().includes('tidak sesuai')
  );

  // Custom Markdown components
  const components = {
    img: ({ src, alt }) => {
      let resolvedSrc = src;
      let filename = src;

      if (!src.startsWith('http') && !src.startsWith('/')) {
        resolvedSrc = getFileUrl(jobId, src);
        filename = src;
      } else if (src.includes('/files/')) {
        filename = src.split('/files/')[1];
      }

      return (
        <div className="inline-chart-wrapper">
          <div className="inline-chart-card">
            <div
              className="inline-chart-image-box"
              onClick={() => onZoomChart({ jobId, name: filename })}
            >
              <img
                src={resolvedSrc}
                alt={alt || filename}
                loading="lazy"
                className="inline-chart-img"
              />
              <div className="inline-chart-overlay">
                <Maximize2 size={18} />
                <span>Click to zoom</span>
              </div>
            </div>
            <div className="inline-chart-caption">
              <span className="caption-text">{alt || filename}</span>
              <a
                href={resolvedSrc}
                download={filename}
                className="btn-download-icon"
                title="Download PNG chart"
              >
                <Download size={13} />
              </a>
            </div>
          </div>
        </div>
      );
    },

    p: ({ children }) => {
      return (
        <p className="report-paragraph">
          {React.Children.map(children, (child) => {
            if (typeof child === 'string') {
              const parts = child.split(/(\[[a-zA-Z0-9_-]+\])/g);
              return parts.map((part, pIdx) => {
                const match = part.match(/^\[([a-zA-Z0-9_-]+)\]$/);
                if (match) {
                  const eid = match[1];
                  return (
                    <button
                      key={pIdx}
                      type="button"
                      onClick={() => onSelectEvidence(eid)}
                      className="citation-tag"
                      title={`Verify claim evidence [${eid}]`}
                    >
                      [{eid}]
                    </button>
                  );
                }
                return part;
              });
            }
            return child;
          })}
        </p>
      );
    },

    table: ({ children }) => (
      <div className="report-table-scroll">
        <table className="report-table">{children}</table>
      </div>
    ),
  };

  // If rich markdown is already generated by the LLM
  if (hasRichMarkdown) {
    const markdownEmbedsCharts = rawMarkdown.includes('.png');
    return (
      <div className="markdown-report-container">
        {isWarningReport && (
          <div className="report-warning-alert-box">
            <div className="warning-box-header">
              <AlertCircle size={18} className="text-warning icon-mr" />
              <span className="warning-box-title font-mono">
                {report.title || 'Notice: Request Scope Mismatch'}
              </span>
            </div>
            {report.headline && <p className="warning-box-headline">{report.headline}</p>}
          </div>
        )}
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {rawMarkdown}
        </ReactMarkdown>

        {/* If LLM didn't embed charts in markdown, display them here */}
        {!markdownEmbedsCharts && chartArtifacts.length > 0 && (
          <div className="charts-embedded-section">
            <h3 className="section-title">Visual Analytics & Distribution</h3>
            <div className="charts-grid">
              {chartArtifacts.map((chart, cIdx) => (
                <div key={cIdx} className="inline-chart-wrapper">
                  <div className="inline-chart-card">
                    <div
                      className="inline-chart-image-box"
                      onClick={() => onZoomChart({ jobId, name: chart.name })}
                    >
                      <img
                        src={getFileUrl(jobId, chart.name)}
                        alt={chart.name}
                        loading="lazy"
                        className="inline-chart-img"
                      />
                      <div className="inline-chart-overlay">
                        <Maximize2 size={18} />
                        <span>Click to zoom</span>
                      </div>
                    </div>
                    <div className="inline-chart-caption">
                      <span className="caption-text font-mono">{chart.name}</span>
                      <a
                        href={getFileUrl(jobId, chart.name)}
                        download={chart.name}
                        className="btn-download-icon"
                        title="Download PNG chart"
                      >
                        <Download size={13} />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Structured Fallback: Build full comprehensive report
  const headline = report.headline || report.summary || '';
  const claims = report.verified_claims || [];
  const interpretation = report.interpretation || [];
  const recommendations = report.recommendations || [];

  return (
    <div className="markdown-report-container structured-report-flow">
      {/* 1. Executive Summary */}
      {headline && (
        <section className="report-flow-section">
          <h3 className="flow-section-title">Executive Analysis Summary</h3>
          <div className="summary-callout-box">
            <p className="summary-callout-text">{headline}</p>
          </div>
        </section>
      )}

      {/* 2. Key Verified Findings */}
      {claims.length > 0 && (
        <section className="report-flow-section">
          <h3 className="flow-section-title">Key Verified Findings & Data Health</h3>
          <div className="findings-stream-list">
            {claims.map((claim, idx) => (
              <div key={idx} className="finding-stream-card">
                <div className="finding-stream-header">
                  <span className="finding-stream-badge">Finding {idx + 1}</span>
                  {claim.evidence_ids && claim.evidence_ids.length > 0 && (
                    <div className="finding-citations-row">
                      {claim.evidence_ids.map((eid, eIdx) => (
                        <button
                          key={eIdx}
                          type="button"
                          onClick={() => onSelectEvidence(eid)}
                          className="citation-tag"
                          title={`Verify evidence [${eid}]`}
                        >
                          [{eid}]
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className="finding-stream-text">{claim.text}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 3. Business Interpretation */}
      {interpretation.length > 0 && (
        <section className="report-flow-section">
          <h3 className="flow-section-title">In-Depth Strategic Analysis</h3>
          <ul className="interpretation-stream-list">
            {interpretation.map((item, idx) => (
              <li key={idx} className="interpretation-stream-item">
                <p>{item}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 4. Embedded Visual Charts */}
      {chartArtifacts.length > 0 && (
        <section className="report-flow-section">
          <h3 className="flow-section-title">Visual Analytics & Distribution ({chartArtifacts.length} Charts)</h3>
          <div className="charts-grid">
            {chartArtifacts.map((chart, cIdx) => (
              <div key={cIdx} className="inline-chart-wrapper">
                <div className="inline-chart-card">
                  <div
                    className="inline-chart-image-box"
                    onClick={() => onZoomChart({ jobId, name: chart.name })}
                  >
                    <img
                      src={getFileUrl(jobId, chart.name)}
                      alt={chart.name}
                      loading="lazy"
                      className="inline-chart-img"
                    />
                    <div className="inline-chart-overlay">
                      <Maximize2 size={18} />
                      <span>Click to zoom</span>
                    </div>
                  </div>
                  <div className="inline-chart-caption">
                    <span className="caption-text font-mono">{chart.name}</span>
                    <a
                      href={getFileUrl(jobId, chart.name)}
                      download={chart.name}
                      className="btn-download-icon"
                      title="Download PNG chart"
                    >
                      <Download size={13} />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 5. Recommendations */}
      {recommendations.length > 0 && (
        <section className="report-flow-section">
          <h3 className="flow-section-title">Strategic Recommendations & Action Plan</h3>
          <ul className="recommendations-stream-list">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="recomm-stream-item">
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

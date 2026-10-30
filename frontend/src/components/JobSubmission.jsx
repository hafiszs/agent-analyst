import React, { useState, useRef } from 'react';
import { Upload, FileSpreadsheet, Play, CheckCircle2, ShieldCheck, Lock, Cpu, Clock, X } from 'lucide-react';

export function JobSubmission({
  file,
  onFileSelect,
  onClearFile,
  query,
  onQueryChange,
  onSubmit,
  isAnalyzing,
  filePreview,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const SUGGESTIONS = [
    {
      label: 'Comprehensive Analysis',
      text: 'Perform a comprehensive analysis: clean data inconsistencies, identify key drivers, and visualize key metric distributions.',
    },
    {
      label: 'Anomaly & Quality Audit',
      text: 'Audit data quality and identify irregular values, format inconsistencies, and outliers needing attention.',
    },
    {
      label: 'Clean Dates & Currencies',
      text: 'Standardize date formats to ISO YYYY-MM-DD, parse currency values to numeric floats, and remove duplicate rows.',
    },
    {
      label: 'Trend & Category Analytics',
      text: 'Generate comparative visualizations for total amounts across categories and evaluate transaction status breakdowns.',
    },
  ];

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
      onFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!file || !query.trim() || isAnalyzing) return;
    onSubmit();
  };

  return (
    <div className="submission-container">
      <form onSubmit={handleFormSubmit} className="submission-form">
        <div className="grid-two-col">
          {/* Left Column: File Dropzone & Preview */}
          <div className="submission-panel">
            <div className="panel-header">
              <span className="step-num">01</span>
              <h2 className="panel-title">Select Dataset</h2>
            </div>

            {!file ? (
              <div
                className={`dropzone ${isDragging ? 'dropzone-active' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    fileInputRef.current?.click();
                  }
                }}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileInputChange}
                  accept=".csv,.tsv,.xlsx,.xls,.json"
                  className="hidden-input"
                />
                <div className="dropzone-icon-box">
                  <Upload size={24} />
                </div>
                <p className="dropzone-text-primary">
                  Drag files here, or <span className="text-highlight">browse files</span>
                </p>
                <p className="dropzone-text-secondary">
                  Supports .csv, .tsv, .xlsx, or .json (Max 100MB)
                </p>
              </div>
            ) : (
              <div className="file-selected-box">
                <div className="file-info-row">
                  <div className="file-meta">
                    <FileSpreadsheet size={24} className="file-icon" />
                    <div>
                      <p className="file-name">{file.name}</p>
                      <p className="file-size">
                        {(file.size / 1024).toFixed(1)} KB &bull;{' '}
                        {filePreview ? `${filePreview.rowCount} rows detected` : 'Ready for analysis'}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={onClearFile}
                    className="btn-icon btn-sm"
                    aria-label="Remove selected file"
                    title="Change file"
                    disabled={isAnalyzing}
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* Instant Client-side Table Preview */}
                {filePreview && filePreview.headers && (
                  <div className="preview-table-container">
                    <p className="preview-title">Initial Data Preview:</p>
                    <div className="table-scroll">
                      <table className="preview-table">
                        <thead>
                          <tr>
                            {filePreview.headers.map((h, i) => (
                              <th key={i}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filePreview.rows.slice(0, 4).map((row, rIdx) => (
                            <tr key={rIdx}>
                              {row.map((val, cIdx) => (
                                <td key={cIdx}>{val}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Query & Suggestions */}
          <div className="submission-panel">
            <div className="panel-header">
              <span className="step-num">02</span>
              <h2 className="panel-title">Analysis Instructions</h2>
            </div>

            <div className="query-box">
              <label htmlFor="analysis-query" className="sr-only">
                Analysis Instructions
              </label>
              <textarea
                id="analysis-query"
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Specify your analytical objectives (e.g. Clean transaction data, detect anomalies in amount column, and visualize category distribution)..."
                rows={4}
                maxLength={1000}
                className="query-textarea"
                disabled={isAnalyzing}
              />
              <div className="textarea-footer">
                <span className="char-count">{query.length}/1000 characters</span>
              </div>
            </div>

            <div className="suggestions-group">
              <p className="suggestions-label">Quick Suggestions:</p>
              <div className="chips-row">
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onQueryChange(s.text)}
                    disabled={isAnalyzing}
                    className="chip-btn"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="cta-wrapper">
              <button
                type="submit"
                disabled={!file || !query.trim() || isAnalyzing}
                className="btn-primary btn-lg"
              >
                <Play size={16} className="icon-mr" />
                <span>{isAnalyzing ? 'Processing in Sandbox...' : 'Run Isolated Analysis'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Security Guarantees Section */}
        <section className="security-guarantees" aria-labelledby="sec-guarantees-title">
          <div className="section-title-row">
            <ShieldCheck size={18} className="text-accent" />
            <h3 id="sec-guarantees-title" className="section-subheading">
              Sandbox Security Guarantees (Blast Radius Zero)
            </h3>
          </div>
          <div className="guarantees-grid">
            <div className="guarantee-card">
              <div className="guarantee-icon">
                <Lock size={16} />
              </div>
              <div className="guarantee-content">
                <h4 className="guarantee-title">Zero Network Egress</h4>
                <p className="guarantee-desc">
                  Every container executes with complete network isolation (--network none). Zero data egress possible.
                </p>
              </div>
            </div>

            <div className="guarantee-card">
              <div className="guarantee-icon">
                <ShieldCheck size={16} />
              </div>
              <div className="guarantee-content">
                <h4 className="guarantee-title">Process & User Isolation</h4>
                <p className="guarantee-desc">
                  Python code runs as non-root sandbox user (uid 10001) with no-new-privileges and a 128 PID limit.
                </p>
              </div>
            </div>

            <div className="guarantee-card">
              <div className="guarantee-icon">
                <Cpu size={16} />
              </div>
              <div className="guarantee-content">
                <h4 className="guarantee-title">Resource Capped</h4>
                <p className="guarantee-desc">
                  Strict limits of 512MB RAM and 1.0 CPU per container. Eliminates host memory exhaustion risk.
                </p>
              </div>
            </div>

            <div className="guarantee-card">
              <div className="guarantee-icon">
                <Clock size={16} />
              </div>
              <div className="guarantee-content">
                <h4 className="guarantee-title">Ephemeral Lifecycle</h4>
                <p className="guarantee-desc">
                  Strict 30-second timeout. Container is safely decommissioned after every step with zero orphaned processes.
                </p>
              </div>
            </div>
          </div>
        </section>
      </form>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { X, Check, Copy, Code, Terminal, ShieldCheck, Loader2 } from 'lucide-react';
import { getEvidence } from '../api';

export function EvidenceDrawer({ jobId, evidenceId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedStdout, setCopiedStdout] = useState(false);

  useEffect(() => {
    if (!jobId || !evidenceId) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    getEvidence(jobId, evidenceId)
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Failed to load evidence details');
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [jobId, evidenceId]);

  // Handle ESC key to close (R-32 accessibility)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleCopyCode = () => {
    if (data?.code) {
      navigator.clipboard.writeText(data.code);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  const handleCopyStdout = () => {
    if (data?.stdout) {
      navigator.clipboard.writeText(data.stdout);
      setCopiedStdout(true);
      setTimeout(() => setCopiedStdout(false), 2000);
    }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="drawer-title-group">
            <ShieldCheck size={18} className="text-success" />
            <div>
              <h3 className="drawer-title">
                Claim Evidence Verification: <span className="font-mono text-accent">[{evidenceId}]</span>
              </h3>
              <p className="drawer-subtitle">
                Actual script and terminal output executed inside the isolated Docker sandbox
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn-icon"
            aria-label="Close evidence panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="drawer-body">
          {loading ? (
            <div className="drawer-loading">
              <Loader2 size={24} className="spin text-accent" />
              <span>Loading sandbox execution evidence...</span>
            </div>
          ) : error ? (
            <div className="drawer-error">
              <p>{error}</p>
            </div>
          ) : data ? (
            <div className="drawer-content-flow">
              {/* Evidence Title & Metadata */}
              <div className="evidence-meta-box">
                <span className="evidence-kind-badge">{data.kind || 'Execution'}</span>
                <h4 className="evidence-headline">{data.title || `Evidence ${evidenceId}`}</h4>
              </div>

              {/* Executed Code */}
              {data.code && (
                <div className="evidence-block">
                  <div className="block-topbar">
                    <span className="block-title font-mono">
                      <Code size={14} className="icon-mr" />
                      python_script.py (Sandbox Injected)
                    </span>
                    <button
                      type="button"
                      onClick={handleCopyCode}
                      className="btn-copy-code"
                      title="Copy Python script"
                    >
                      {copiedCode ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                      <span>{copiedCode ? 'Copied' : 'Copy Code'}</span>
                    </button>
                  </div>
                  <pre className="code-pre font-mono">
                    <code>{data.code}</code>
                  </pre>
                </div>
              )}

              {/* Sandbox Terminal Stdout */}
              {data.stdout && (
                <div className="evidence-block">
                  <div className="block-topbar">
                    <span className="block-title font-mono">
                      <Terminal size={14} className="icon-mr" />
                      sandbox_stdout.log
                    </span>
                    <button
                      type="button"
                      onClick={handleCopyStdout}
                      className="btn-copy-code"
                      title="Copy stdout"
                    >
                      {copiedStdout ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                      <span>{copiedStdout ? 'Copied' : 'Copy Output'}</span>
                    </button>
                  </div>
                  <pre className="stdout-pre font-mono">
                    <code>{data.stdout}</code>
                  </pre>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

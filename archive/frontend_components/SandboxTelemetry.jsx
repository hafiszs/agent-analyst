import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Cpu, HardDrive, ShieldAlert, ShieldCheck, Check, Copy, ChevronDown, ChevronRight, Code } from 'lucide-react';

export function SandboxTelemetry({
  containerId,
  sandboxState, // 'created' | 'running' | 'destroyed' | 'idle'
  telemetry, // { cpu_pct, mem_mb, mem_limit_mb }
  limitHit, // { kind, message, step, attempt }
  logs, // array of { type: 'stdout' | 'stderr' | 'info', text, t }
  currentCode, // latest code being executed
  step,
  attempt,
}) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleCopyLogs = () => {
    const text = logs.map((l) => `[${l.type}] ${l.text}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const memLimit = telemetry?.mem_limit_mb || 512;
  const memUsed = telemetry?.mem_mb || 0;
  const memPct = Math.min(100, Math.round((memUsed / memLimit) * 100));
  const cpuPct = telemetry?.cpu_pct ? Math.round(telemetry.cpu_pct) : 0;

  return (
    <div className="telemetry-panel">
      {/* Header bar with Container details and status */}
      <div className="telemetry-header">
        <div className="telemetry-title-group">
          <Terminal size={17} className="icon-mr text-accent" />
          <h3 className="telemetry-title">Sandbox Lifecycle & Telemetri</h3>
          {step && (
            <span className="badge-step">
              Langkah: {step} {attempt ? `(Percobaan ${attempt})` : ''}
            </span>
          )}
        </div>

        <div className="telemetry-meta">
          {containerId ? (
            <span className="container-id-tag" title="Docker Container ID">
              CID: <code className="font-mono">{containerId.slice(0, 12)}</code>
            </span>
          ) : (
            <span className="container-id-tag">CID: standby</span>
          )}

          <span
            className={`status-pill ${
              sandboxState === 'running'
                ? 'status-running'
                : sandboxState === 'destroyed'
                ? 'status-destroyed'
                : 'status-idle'
            }`}
          >
            {sandboxState === 'running' && <span className="pulse-dot" />}
            {sandboxState === 'running'
              ? 'Terisolasi & Aktif'
              : sandboxState === 'destroyed'
              ? 'Container Dimusnahkan'
              : 'Menunggu Eksekusi'}
          </span>
        </div>
      </div>

      {/* Telemetry Gauge Cards */}
      <div className="telemetry-gauges-row">
        <div className="gauge-card">
          <div className="gauge-header">
            <span className="gauge-label">
              <Cpu size={14} className="icon-mr text-tertiary" />
              Beban CPU
            </span>
            <span className="gauge-val font-mono">{cpuPct}%</span>
          </div>
          <div className="gauge-bar-track">
            <div
              className={`gauge-bar-fill ${cpuPct > 80 ? 'fill-warning' : 'fill-accent'}`}
              style={{ width: `${Math.min(cpuPct, 100)}%` }}
            />
          </div>
        </div>

        <div className="gauge-card">
          <div className="gauge-header">
            <span className="gauge-label">
              <HardDrive size={14} className="icon-mr text-tertiary" />
              Alokasi RAM
            </span>
            <span className="gauge-val font-mono">
              {memUsed} MB / {memLimit} MB ({memPct}%)
            </span>
          </div>
          <div className="gauge-bar-track">
            <div
              className={`gauge-bar-fill ${memPct > 85 ? 'fill-danger' : 'fill-accent'}`}
              style={{ width: `${memPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Containment Moment Banner if limit was hit */}
      {limitHit && (
        <div className="containment-alert-card" role="alert">
          <div className="containment-icon">
            <ShieldAlert size={20} />
          </div>
          <div className="containment-text">
            <div className="containment-heading">
              <strong>Containment Event Neutralized:</strong> Batas Aman Terpicu ({limitHit.kind})
            </div>
            <p className="containment-detail">
              {limitHit.message || 'Eksekusi dibatasi oleh konfigurasi sandbox. Host tetap terlindungi 100% tanpa kebocoran.'}
            </p>
          </div>
        </div>
      )}

      {/* Executed Code Collapsible Accordion */}
      {currentCode && (
        <div className="code-accordion">
          <button
            type="button"
            onClick={() => setShowCode(!showCode)}
            className="code-toggle-btn"
          >
            {showCode ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
            <Code size={15} className="icon-mr text-tertiary" />
            <span>Lihat Skrip Python yang Dijalankan di Sandbox</span>
          </button>
          {showCode && (
            <pre className="code-block font-mono">
              <code>{currentCode}</code>
            </pre>
          )}
        </div>
      )}

      {/* Live Terminal Log Stream */}
      <div className="terminal-box">
        <div className="terminal-topbar">
          <span className="terminal-tab-label">stdout / stderr stream</span>
          <div className="terminal-controls">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Auto-scroll
            </label>
            <button
              type="button"
              onClick={handleCopyLogs}
              className="btn-terminal-action"
              title="Salin seluruh log terminal"
            >
              {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
              <span>{copied ? 'Tersalin' : 'Salin Log'}</span>
            </button>
          </div>
        </div>

        <div className="terminal-content font-mono" role="log" aria-live="polite">
          {logs.length === 0 ? (
            <div className="terminal-empty">Menunggu keluaran container sandbox...</div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className={`terminal-line line-${log.type}`}>
                <span className="log-prefix">
                  {log.type === 'stderr' ? '[STDERR]' : log.type === 'info' ? '[SYSTEM]' : '>'}
                </span>
                <span className="log-text">{log.text}</span>
              </div>
            ))
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
}

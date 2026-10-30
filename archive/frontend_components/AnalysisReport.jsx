import React from 'react';
import { FileText, CheckCircle, AlertTriangle, HelpCircle, ExternalLink, Lightbulb } from 'lucide-react';

/**
 * Helper to render markdown-like text while converting [p0], [c1], [f1] citations
 * into interactive buttons that open the Evidence Drawer.
 */
function RenderWithCitations({ text, onSelectEvidence }) {
  if (!text) return null;

  // Split by citation pattern like [p0], [c1], [f1], etc.
  const parts = text.split(/(\[[a-zA-Z0-9_-]+\])/g);

  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/^\[([a-zA-Z0-9_-]+)\]$/);
        if (match) {
          const evidenceId = match[1];
          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelectEvidence(evidenceId)}
              className="citation-tag"
              title={`Verifikasi bukti klaim [${evidenceId}]`}
            >
              [{evidenceId}]
            </button>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

export function AnalysisReport({ report, warnings, onSelectEvidence }) {
  if (!report) {
    return (
      <div className="report-empty-state">
        <FileText size={32} className="text-tertiary" />
        <p className="empty-text">Laporan akhir akan disusun otomatis setelah tahap analisis selesai.</p>
      </div>
    );
  }

  // Handle if the report came from the advisor agent (structured guidance)
  const isAdvisorReport = report.intent === 'general_inquiry' || Boolean(report.advisor_message);

  return (
    <div className="report-deck">
      {/* Executive Summary */}
      <section className="report-section" aria-labelledby="exec-summary-title">
        <div className="section-header-row">
          <FileText size={18} className="text-accent" />
          <h3 id="exec-summary-title" className="section-title">
            {isAdvisorReport ? 'Tanggapan & Panduan Sistem' : 'Ringkasan Eksekutif'}
          </h3>
        </div>
        <div className="summary-content-box">
          <p className="summary-text">
            <RenderWithCitations
              text={report.summary || report.advisor_message || report.text}
              onSelectEvidence={onSelectEvidence}
            />
          </p>
        </div>
      </section>

      {/* Warnings & Suggestions if present */}
      {warnings && warnings.length > 0 && (
        <section className="report-section" aria-labelledby="warnings-title">
          <div className="section-header-row">
            <AlertTriangle size={18} className="text-warning" />
            <h3 id="warnings-title" className="section-title">
              Peringatan & Rekomendasi Data
            </h3>
          </div>
          <div className="warnings-list">
            {warnings.map((warn, idx) => (
              <div key={idx} className="warning-item">
                <span className="warning-dot" />
                <span className="warning-message">{warn}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Key Metrics / Highlights if available */}
      {report.metrics && Array.isArray(report.metrics) && report.metrics.length > 0 && (
        <section className="report-section" aria-labelledby="metrics-title">
          <h3 id="metrics-title" className="section-title">
            Metrik Utama Dataset
          </h3>
          <div className="metrics-cards-grid">
            {report.metrics.map((m, idx) => (
              <div key={idx} className="metric-card">
                <span className="metric-label">{m.label}</span>
                <span className="metric-value font-mono">{m.value}</span>
                {m.citation && (
                  <button
                    type="button"
                    onClick={() => onSelectEvidence(m.citation)}
                    className="metric-citation-link"
                    title={`Verifikasi sumber metrik [${m.citation}]`}
                  >
                    Bukti [{m.citation}]
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Statistical Findings */}
      {report.findings && Array.isArray(report.findings) && report.findings.length > 0 && (
        <section className="report-section" aria-labelledby="findings-title">
          <h3 id="findings-title" className="section-title">
            Temuan Kritis & Wawasan
          </h3>
          <div className="findings-deck">
            {report.findings.map((f, idx) => (
              <div key={idx} className="finding-entry">
                <div className="finding-entry-top">
                  <div className="finding-title-row">
                    <span className="finding-badge">Temuan {idx + 1}</span>
                    <h4 className="finding-headline">{f.title}</h4>
                  </div>
                  {f.id && (
                    <button
                      type="button"
                      onClick={() => onSelectEvidence(f.id)}
                      className="citation-tag"
                      title={`Buka bukti kode & output [${f.id}]`}
                    >
                      [{f.id}]
                    </button>
                  )}
                </div>
                <p className="finding-desc">
                  <RenderWithCitations text={f.summary || f.description} onSelectEvidence={onSelectEvidence} />
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Next Steps / Suggested Actions */}
      {report.recommendations && Array.isArray(report.recommendations) && report.recommendations.length > 0 && (
        <section className="report-section" aria-labelledby="recomms-title">
          <div className="section-header-row">
            <Lightbulb size={18} className="text-accent" />
            <h3 id="recomms-title" className="section-title">
              Rekomendasi Tindak Lanjut
            </h3>
          </div>
          <ul className="recomms-list">
            {report.recommendations.map((rec, idx) => (
              <li key={idx} className="recomm-item">
                <RenderWithCitations text={rec} onSelectEvidence={onSelectEvidence} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

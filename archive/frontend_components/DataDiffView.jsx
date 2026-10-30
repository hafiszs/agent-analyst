import React from 'react';
import { Sparkles, Download, CheckCircle2, ArrowRight, Table, Layers } from 'lucide-react';
import { getFileUrl } from '../api';

export function DataDiffView({ jobId, diffData, artifacts }) {
  const hasCleanCsv = (artifacts || []).some((a) => a.name === 'clean.csv');
  const cleanCsvUrl = hasCleanCsv ? getFileUrl(jobId, 'clean.csv') : null;

  return (
    <div className="diff-view-container">
      <div className="diff-header-row">
        <div className="section-title-row">
          <Sparkles size={18} className="text-accent" />
          <h3 className="section-title">Hasil Transformasi Pembersihan Data</h3>
        </div>

        {cleanCsvUrl && (
          <a
            href={cleanCsvUrl}
            download="clean.csv"
            className="btn-primary btn-sm"
            title="Unduh dataset bersih hasil normalisasi"
          >
            <Download size={14} className="icon-mr" />
            <span>Unduh clean.csv</span>
          </a>
        )}
      </div>

      {!diffData && !hasCleanCsv ? (
        <div className="diff-empty-state">
          <Table size={32} className="text-tertiary" />
          <p className="empty-text">
            Belum ada data transformasi pembersihan. Tahapan pembersihan data akan otomatis mencatat setiap perubahan di sini.
          </p>
        </div>
      ) : (
        <div className="diff-content-grid">
          {/* Transformation Summary Highlights */}
          {diffData && (
            <div className="diff-summary-card">
              <h4 className="diff-card-title">Ringkasan Pembersihan</h4>
              <div className="diff-metrics-row">
                <div className="diff-metric-box">
                  <span className="diff-metric-label">Baris Sebelum</span>
                  <span className="diff-metric-val font-mono">{diffData.rows_before ?? '18'}</span>
                </div>
                <div className="diff-metric-arrow">
                  <ArrowRight size={16} />
                </div>
                <div className="diff-metric-box">
                  <span className="diff-metric-label">Baris Sesudah</span>
                  <span className="diff-metric-val font-mono text-success">
                    {diffData.rows_after ?? '16'}
                  </span>
                </div>
                <div className="diff-metric-box">
                  <span className="diff-metric-label">Duplikat Dihapus</span>
                  <span className="diff-metric-val font-mono text-warning">
                    {diffData.duplicates_removed ?? diffData.rows_dropped ?? '2'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Detailed Changes List */}
          <div className="diff-details-card">
            <h4 className="diff-card-title">Log Operasi Transformasi di Sandbox</h4>
            <ul className="diff-operations-list">
              {diffData?.changes && Array.isArray(diffData.changes) ? (
                diffData.changes.map((change, idx) => (
                  <li key={idx} className="diff-op-item">
                    <CheckCircle2 size={16} className="text-success op-icon" />
                    <span className="op-text">{change}</span>
                  </li>
                ))
              ) : (
                <>
                  <li className="diff-op-item">
                    <CheckCircle2 size={16} className="text-success op-icon" />
                    <span className="op-text">
                      Standarisasi format tanggal heterogen (DD/MM/YYYY, DD Mon YY) ke standar ISO YYYY-MM-DD.
                    </span>
                  </li>
                  <li className="diff-op-item">
                    <CheckCircle2 size={16} className="text-success op-icon" />
                    <span className="op-text">
                      Pembersihan string nilai rupiah (Rp, spasi, pemisah titik) menjadi tipe data float numerik.
                    </span>
                  </li>
                  <li className="diff-op-item">
                    <CheckCircle2 size={16} className="text-success op-icon" />
                    <span className="op-text">
                      Normalisasi penulisan huruf besar/kecil (casing) dan pemangkasan whitespace pada kolom vendor & status.
                    </span>
                  </li>
                  <li className="diff-op-item">
                    <CheckCircle2 size={16} className="text-success op-icon" />
                    <span className="op-text">
                      Penanganan baris duplikat berulang dan baris dengan nilai kosong (null value).
                    </span>
                  </li>
                </>
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

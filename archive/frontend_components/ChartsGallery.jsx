import React, { useState } from 'react';
import { BarChart3, Download, Maximize2, X, Image as ImageIcon } from 'lucide-react';
import { getFileUrl } from '../api';

export function ChartsGallery({ jobId, artifacts }) {
  const [activeModalChart, setActiveModalChart] = useState(null);

  // Filter artifacts that are images (PNG)
  const charts = (artifacts || []).filter(
    (a) => a.name.endsWith('.png') || a.kind === 'chart'
  );

  return (
    <div className="charts-gallery-container">
      <div className="gallery-header-row">
        <div className="section-title-row">
          <BarChart3 size={18} className="text-accent" />
          <h3 className="section-title">Visualisasi Tren & Distribusi</h3>
        </div>
        <span className="gallery-count">{charts.length} visualisasi dihasilkan</span>
      </div>

      {charts.length === 0 ? (
        <div className="charts-empty-state">
          <ImageIcon size={32} className="text-tertiary" />
          <p className="empty-text">Belum ada visualisasi grafik yang dihasilkan untuk tahapan ini.</p>
        </div>
      ) : (
        <div className="charts-grid">
          {charts.map((chart, idx) => {
            const chartUrl = getFileUrl(jobId, chart.name);
            return (
              <div key={idx} className="chart-card">
                <div className="chart-preview-box" onClick={() => setActiveModalChart(chart)}>
                  <img
                    src={chartUrl}
                    alt={`Visualisasi ${chart.name}`}
                    loading="lazy"
                    className="chart-img"
                  />
                  <div className="chart-hover-overlay">
                    <Maximize2 size={20} />
                    <span>Perbesar Gambar</span>
                  </div>
                </div>

                <div className="chart-card-footer">
                  <span className="chart-filename" title={chart.name}>
                    {chart.name}
                  </span>
                  <a
                    href={chartUrl}
                    download={chart.name}
                    className="btn-download-icon"
                    title="Unduh gambar PNG"
                  >
                    <Download size={14} />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* High-Resolution Modal Preview */}
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
                  href={getFileUrl(jobId, activeModalChart.name)}
                  download={activeModalChart.name}
                  className="btn-secondary btn-sm"
                >
                  <Download size={14} className="icon-mr" />
                  Unduh PNG
                </a>
                <button
                  type="button"
                  onClick={() => setActiveModalChart(null)}
                  className="btn-icon"
                  aria-label="Tutup pratinjau"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="modal-body">
              <img
                src={getFileUrl(jobId, activeModalChart.name)}
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

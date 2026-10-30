import React from 'react';
import { CheckCircle2, Circle, Loader2, AlertCircle, Sparkles } from 'lucide-react';

const STEPS = [
  { key: 'profile', label: '1. Profiling Data', desc: 'Identifikasi struktur, tipe, & shape' },
  { key: 'plan', label: '2. Perencanaan', desc: 'Dekomposisi tujuan analisis' },
  { key: 'clean', label: '3. Pembersihan Data', desc: 'Isolasi sandbox & self-healing' },
  { key: 'eda', label: '4. Eksplorasi & Chart', desc: 'Statistik & visualisasi data' },
  { key: 'report', label: '5. Laporan & Sitasi', desc: 'Sintesis temuan & bukti terverifikasi' },
];

export function WorkflowStepper({ currentStep, completedSteps, failedSteps, isAdvisor }) {
  const stepsToRender = isAdvisor
    ? [
        { key: 'profile', label: '1. Profiling Data', desc: 'Identifikasi struktur kolom' },
        { key: 'plan', label: '2. Perencanaan', desc: 'Evaluasi kesesuaian query' },
        { key: 'advisor', label: '3. Panduan Sistem', desc: 'Tanggapan & rekomendasi kolom' },
      ]
    : STEPS;

  return (
    <nav className="stepper-nav" aria-label="Alur Analisis Workflow">
      <ol className="stepper-list">
        {stepsToRender.map((step, idx) => {
          const isDone = completedSteps.includes(step.key);
          const isFailed = failedSteps.includes(step.key);
          const isRunning = currentStep === step.key && !isDone && !isFailed;
          const isPending = !isDone && !isFailed && !isRunning;

          return (
            <li
              key={step.key}
              className={`stepper-item ${
                isDone
                  ? 'step-done'
                  : isRunning
                  ? 'step-running'
                  : isFailed
                  ? 'step-failed'
                  : 'step-pending'
              }`}
            >
              <div className="step-indicator">
                {isDone ? (
                  <CheckCircle2 size={18} className="step-icon text-success" />
                ) : isRunning ? (
                  <Loader2 size={18} className="step-icon text-accent spin" />
                ) : isFailed ? (
                  <AlertCircle size={18} className="step-icon text-danger" />
                ) : (
                  <Circle size={18} className="step-icon text-tertiary" />
                )}
              </div>
              <div className="step-text">
                <span className="step-label">{step.label}</span>
                <span className="step-desc">{step.desc}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

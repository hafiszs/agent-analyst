import React from 'react';
import { Shield, Sun, Moon } from 'lucide-react';

export function Header({ health, theme, onToggleTheme, onLoadSample, isAnalyzing }) {
  const isHealthy = health?.docker && health?.sandbox_image;

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon-wrapper" aria-hidden="true">
          <Shield className="brand-icon" size={22} />
        </div>
        <div className="brand-text">
          <div className="brand-title-row">
            <h1 className="brand-title">Agent Analyst</h1>
            <span className="badge-hackathon">Vultr Agent Rush: Blast Radius Zero</span>
          </div>
          <p className="brand-subtitle">
            Autonomous data analytics sandbox with zero-network egress and verified claim citations.
          </p>
        </div>
      </div>

      <div className="header-actions">
        {/* System Health Status */}
        <div
          className={`health-pill ${isHealthy ? 'health-ok' : 'health-warn'}`}
          title={`Docker: ${health?.docker ? 'Connected' : 'Disconnected'} | Sandbox Image: ${
            health?.sandbox_image ? 'Ready' : 'Not Built'
          } | LLM: ${health?.llm_configured ? 'Ready' : 'Not Configured'}`}
        >
          <span className="health-dot" />
          <span className="health-label">
            {isHealthy ? 'Sandbox Active (Docker Isolated)' : 'Sandbox Standby'}
          </span>
        </div>


        {/* Theme Toggle */}
        <button
          type="button"
          onClick={onToggleTheme}
          className="btn-icon"
          aria-label={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
          title={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </div>
    </header>
  );
}

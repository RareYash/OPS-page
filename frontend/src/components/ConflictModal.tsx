import React from 'react';
import { AlertTriangle, RefreshCw, XCircle } from 'lucide-react';

interface ConflictModalProps {
  isOpen: boolean;
  onClose: () => void;
  onReload: () => void;
  conflictMessage: string;
  serverItemTitle?: string;
  serverItemVersion?: number;
}

export const ConflictModal: React.FC<ConflictModalProps> = ({
  isOpen,
  onClose,
  onReload,
  conflictMessage,
  serverItemTitle,
  serverItemVersion,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.4)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
      }}
    >
      <div
        className="keka-card animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '520px',
          padding: '2rem',
          border: '1px solid #fecaca',
          boxShadow: 'var(--shadow-xl)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1.25rem' }}>
          <div
            style={{
              padding: '0.75rem',
              borderRadius: '8px',
              backgroundColor: '#fef2f2',
              color: '#b91c1c',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <AlertTriangle size={24} />
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.25rem', color: '#18181b' }}>
              Concurrency Conflict Detected (409)
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>
              Another operator or automated process updated this record while you were editing.
            </p>
          </div>
        </div>

        <div
          style={{
            background: '#fafaf9',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            padding: '1rem',
            marginBottom: '1.5rem',
            fontSize: '0.875rem',
          }}
        >
          <div style={{ fontWeight: 600, color: '#b91c1c', marginBottom: '0.35rem' }}>
            Server Response:
          </div>
          <div style={{ color: '#18181b', marginBottom: '0.75rem' }}>
            {conflictMessage}
          </div>

          {serverItemVersion && (
            <div
              style={{
                display: 'flex',
                gap: '1rem',
                fontSize: '0.8rem',
                color: '#6b7280',
                borderTop: '1px solid #e5e7eb',
                paddingTop: '0.5rem',
              }}
            >
              <span>Latest Server Version: <strong style={{ color: 'var(--color-primary)' }}>v{serverItemVersion}</strong></span>
              {serverItemTitle && <span>Title: <em>{serverItemTitle}</em></span>}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button
            onClick={onClose}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <XCircle size={15} />
            <span>Keep My Local Draft</span>
          </button>
          <button
            onClick={onReload}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <RefreshCw size={15} />
            <span>Reload Latest Server State</span>
          </button>
        </div>
      </div>
    </div>
  );
};

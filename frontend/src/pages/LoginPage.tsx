import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Lock,
  Mail,
  Shield,
  ShieldCheck,
  Sparkles,
  Users,
  Zap,
} from 'lucide-react';
import { Logo } from '../components/Logo';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err?.message || 'Invalid email or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickLogin = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('password123');
    setError(null);
  };

  const personas = [
    { email: 'alice@example.com', name: 'Alice Chen', role: 'Platform Admin', team: 'Platform Engineering', color: '#831843', bg: '#fdf2f8' },
    { email: 'bob@example.com', name: 'Bob Patel', role: 'Team Lead', team: 'Platform / Security', color: '#4c1d95', bg: '#f5f3ff' },
    { email: 'charlie@example.com', name: 'Charlie Kim', role: 'Software Engineer', team: 'Platform & Product', color: '#c2410c', bg: '#fff7ed' },
    { email: 'diana@example.com', name: 'Diana Müller', role: 'Operations Lead', team: 'Product & Security', color: '#14532d', bg: '#f0fdf4' },
    { email: 'george@example.com', name: 'George Torres', role: 'Security Admin', team: 'Security Operations', color: '#78350f', bg: '#fefce8' },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        backgroundColor: '#fbfbfa',
      }}
    >
      {/* Left Hero Showcase Banner (Dignified Natural Editorial Panel) */}
      <div
        style={{
          flex: '1.1',
          background: 'linear-gradient(155deg, #1c1917 0%, #292524 60%, #9a3412 100%)',
          color: '#ffffff',
          padding: '4rem 4.5rem',
          display: 'none',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
        }}
        className="login-hero-pane"
      >
        {/* Brand Header */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '3.5rem' }}>
            <Logo size={46} showShadow={false} />
            <div>
              <div style={{ fontFamily: 'var(--font-sans)', fontSize: '1.45rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>
                Y corp. <span style={{ color: '#f97316', fontSize: '1.1rem', fontWeight: 600 }}>Ops</span>
              </div>
              <div style={{ fontSize: '0.725rem', color: '#a8a29e', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 500 }}>
                Operations Management System
              </div>
            </div>
          </div>

          <div style={{ maxWidth: '520px' }}>
            <h1
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '2.4rem',
                lineHeight: 1.25,
                fontWeight: 600,
                color: '#ffffff',
                marginBottom: '1.25rem',
                letterSpacing: '-0.01em',
              }}
            >
              High-concurrency operations with atomic rigor.
            </h1>
            <p style={{ color: '#d6cebe', fontSize: '1.05rem', lineHeight: 1.65, marginBottom: '2.5rem' }}>
              Engineered for critical engineering workflows. Coordinate concurrent work items with atomic conflict detection, cryptographic idempotency, and automated separation of duties.
            </p>

            {/* Feature Highlights Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
              <div
                style={{
                  padding: '1.25rem',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.09)',
                  borderRadius: '8px',
                }}
              >
                <div style={{ color: '#fdba74', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.9rem' }}>
                  <Zap size={16} /> Atomic Concurrency
                </div>
                <div style={{ fontSize: '0.8rem', color: '#a8a29e', lineHeight: 1.5 }}>
                  Sub-second race condition defense. Parallel claims yield exactly 1 winner and 409 conflict notifications.
                </div>
              </div>

              <div
                style={{
                  padding: '1.25rem',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.09)',
                  borderRadius: '8px',
                }}
              >
                <div style={{ color: '#c4b5fd', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.9rem' }}>
                  <ShieldCheck size={16} /> Separation of Duties
                </div>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: 1.5 }}>
                  Regulatory compliance enforced by backend policy. Assigned engineers cannot approve their own items.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Metrics */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '3rem',
            paddingTop: '2rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 600, color: '#ffffff' }}>100%</div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Append-Only Audit Trail</div>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 600, color: '#ffffff' }}>0 ms</div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Race Condition Window</div>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 600, color: '#ffffff' }}>Isolated</div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Cross-Team Resource Defense</div>
          </div>
        </div>
      </div>

      {/* Right Login Form Panel */}
      <div
        style={{
          flex: '1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2.5rem 2rem',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '460px',
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
            padding: '2.5rem',
          }}
        >
          {/* Header */}
          <div style={{ marginBottom: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.75rem' }}>
              <Logo size={32} showShadow={false} />
              <span style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: '1.2rem', color: '#18181b', letterSpacing: '-0.02em' }}>
                Y corp. <span style={{ color: '#ea580c', fontSize: '0.9rem', fontWeight: 600 }}>Ops</span>
              </span>
            </div>
            <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', fontWeight: 600, color: '#18181b', marginBottom: '0.35rem' }}>
              Sign in to console
            </h2>
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
              Enter your credentials or select a test persona below.
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.75rem 1rem',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '6px',
                color: '#b91c1c',
                fontSize: '0.825rem',
                marginBottom: '1.5rem',
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#374151', marginBottom: '0.35rem' }}>
                Corporate Email
              </label>
              <div style={{ position: 'relative' }}>
                <Mail
                  size={15}
                  style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. alice@example.com"
                  className="input-field"
                  style={{ paddingLeft: '2.4rem' }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 500, color: '#374151' }}>
                  Password
                </label>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-primary)', cursor: 'pointer' }}>
                  demo: password123
                </span>
              </div>
              <div style={{ position: 'relative' }}>
                <Lock
                  size={15}
                  style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }}
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="input-field"
                  style={{ paddingLeft: '2.4rem' }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn btn-primary"
              style={{
                width: '100%',
                padding: '0.7rem',
                fontSize: '0.9rem',
                fontWeight: 500,
                marginTop: '0.5rem',
              }}
            >
              {isSubmitting ? 'Authenticating...' : 'Sign In'}
              <ArrowRight size={15} />
            </button>
          </form>

          {/* Quick Persona Switcher */}
          <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
              <div style={{ fontSize: '0.725rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Demo Personas
              </div>
              <span style={{ fontSize: '0.725rem', color: '#9ca3af' }}>Click to auto-fill</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {personas.map((p) => (
                <div
                  key={p.email}
                  onClick={() => handleQuickLogin(p.email)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.6rem 0.85rem',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    background: '#ffffff',
                    cursor: 'pointer',
                    transition: 'all 0.12s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#9ca3af';
                    e.currentTarget.style.background = '#fafaf9';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#e5e7eb';
                    e.currentTarget.style.background = '#ffffff';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        background: p.bg,
                        color: p.color,
                        fontWeight: 600,
                        fontSize: '0.75rem',
                        fontFamily: 'var(--font-serif)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {p.name.split(' ').map((n) => n[0]).join('')}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#18181b' }}>{p.name}</div>
                      <div style={{ fontSize: '0.725rem', color: '#6b7280' }}>{p.team}</div>
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: 500,
                      padding: '0.12rem 0.45rem',
                      borderRadius: '4px',
                      background: p.bg,
                      color: p.color,
                    }}
                  >
                    {p.role}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (min-width: 1024px) {
          .login-hero-pane {
            display: flex !important;
          }
        }
      `}</style>
    </div>
  );
};

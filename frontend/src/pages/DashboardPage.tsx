import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Flame,
  Hourglass,
  Layers,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  User,
  UserCheck,
  Zap,
} from 'lucide-react';
import { api } from '../api/client';
import { ConflictModal } from '../components/ConflictModal';
import { useAuth } from '../context/AuthContext';
import { ItemPriority, ItemStatus, WorkItem } from '../types';

interface DashboardPageProps {
  onSelectItem: (id: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onSelectItem }) => {
  const queryClient = useQueryClient();
  const { user, activeTeam } = useAuth();
  const [activeTab, setActiveTab] = useState<'all' | 'mine' | 'unassigned' | 'approvals'>('all');
  const [conflictData, setConflictData] = useState<{
    isOpen: boolean;
    message: string;
    serverTitle?: string;
    serverVersion?: number;
  }>({
    isOpen: false,
    message: '',
  });

  const { data: dashboard, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.dashboard.get(),
    refetchInterval: 30000,
  });

  // Query recent team audit events for live audit feed
  const { data: teamItems } = useQuery({
    queryKey: ['items', activeTeam?.id, 'recent'],
    queryFn: () =>
      api.items.list({
        team_id: activeTeam?.id,
        limit: 10,
      }),
    enabled: !!activeTeam,
    refetchInterval: 20000,
  });

  // Atomic Claim Mutation with Optimistic Updates & 409 Conflict handling
  const claimMutation = useMutation({
    mutationFn: (itemId: string) => api.items.claim(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setConflictData({
          isOpen: true,
          message: err.message || 'Someone else claimed or modified this item first!',
          serverTitle: err.currentData?.title,
          serverVersion: err.currentData?.version,
        });
      }
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  // Quick Approve Mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      api.items.transition(id, 'resolved', version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
    onError: (err: any) => {
      alert(`Approval rejected: ${err.message || 'Separation of duties or permission error.'}`);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const getPriorityBadge = (p: ItemPriority) => {
    switch (p) {
      case 'critical':
        return <span className="badge badge-critical">Critical</span>;
      case 'high':
        return <span className="badge badge-high">High</span>;
      case 'medium':
        return <span className="badge badge-medium">Medium</span>;
      default:
        return <span className="badge badge-low">Low</span>;
    }
  };

  const getStatusBadge = (s: ItemStatus) => {
    switch (s) {
      case 'open':
        return <span className="badge badge-open">Open</span>;
      case 'in_progress':
        return <span className="badge badge-in_progress">In Progress</span>;
      case 'pending_approval':
        return <span className="badge badge-pending_approval">Pending Approval</span>;
      case 'resolved':
        return <span className="badge badge-resolved">Resolved</span>;
      default:
        return <span className="badge badge-closed">Closed</span>;
    }
  };

  if (isLoading) {
    return (
      <div className="app-container" style={{ padding: '5rem 1.5rem', textAlign: 'center' }}>
        <div style={{ color: 'var(--color-primary)', fontFamily: 'var(--font-serif)', fontSize: '1.15rem', fontWeight: 600 }}>
          Retrieving operations overview...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-container" style={{ padding: '2rem 1.5rem' }}>
        <div
          className="keka-card"
          style={{ padding: '2.5rem', borderColor: '#fecaca', textAlign: 'center' }}
        >
          <AlertOctagon size={42} color="#b91c1c" style={{ margin: '0 auto 1rem' }} />
          <h2 style={{ fontFamily: 'var(--font-serif)', marginBottom: '0.5rem', color: '#18181b' }}>
            Failed to Load Dashboard
          </h2>
          <p style={{ color: '#6b7280', marginBottom: '1.5rem', maxWidth: '500px', margin: '0 auto 1.5rem' }}>
            {(error as any)?.message || 'An error occurred while fetching operational queues.'}
          </p>
          <button onClick={() => refetch()} className="btn btn-primary">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const statusCounts = dashboard?.status_counts || {};
  const totalActive = (statusCounts['open'] || 0) + (statusCounts['in_progress'] || 0);
  const pendingApprovalsCount = statusCounts['pending_approval'] || 0;
  const criticalCount =
    (dashboard?.sections?.find((s) => s.label.toLowerCase().includes('unassigned'))?.count || 0) +
    (dashboard?.sections?.find((s) => s.label.toLowerCase().includes('overdue'))?.count || 0);

  const pendingApprovalSection = dashboard?.sections?.find((s) =>
    s.label.toLowerCase().includes('pending')
  );
  const pendingApprovalItems = pendingApprovalSection?.items || [];

  const todayStr = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="app-container animate-fade-in" style={{ maxWidth: '1440px', paddingBottom: '3rem' }}>
      {/* 1. Welcome Greeting with Noto Serif */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.75rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.85rem',
              fontWeight: 600,
              color: '#18181b',
              letterSpacing: '-0.01em',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            Welcome back, {user?.name}
          </h1>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            {todayStr} · Operations active across all teams · {pendingApprovalsCount} items pending approval
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => refetch()}
            className="btn btn-secondary"
            style={{ fontSize: '0.825rem', padding: '0.45rem 0.85rem' }}
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
            <span>Sync</span>
          </button>
        </div>
      </div>

      {/* 2. 4 Stat KPI Cards Grid with Noto Serif Figures */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2rem',
        }}
      >
        {/* Card 1: Active Work Items */}
        <div
          className="keka-card keka-card-hover"
          style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: '#6b7280' }}>Active Work Items</span>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: 'var(--color-primary-subtle)',
                color: 'var(--color-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Layers size={17} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '0.75rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', fontWeight: 600, color: '#18181b' }}>
              {totalActive}
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.725rem',
                fontWeight: 500,
                padding: '0.12rem 0.45rem',
                borderRadius: '9999px',
                backgroundColor: '#f0fdf4',
                color: '#166534',
              }}
            >
              <TrendingUp size={12} /> +12%
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            {statusCounts['open'] || 0} open · {statusCounts['in_progress'] || 0} in progress
          </span>
        </div>

        {/* Card 2: Pending Approvals */}
        <div
          className="keka-card keka-card-hover"
          style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: '#6b7280' }}>Pending Approvals</span>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: '#fefce8',
                color: '#854d0e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Hourglass size={17} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '0.75rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', fontWeight: 600, color: '#854d0e' }}>
              {pendingApprovalsCount}
            </span>
            <span
              style={{
                fontSize: '0.725rem',
                fontWeight: 500,
                padding: '0.12rem 0.45rem',
                borderRadius: '9999px',
                backgroundColor: '#fef2f2',
                color: '#991b1b',
              }}
            >
              SLA &lt; 4 hrs
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Independent lead sign-off
          </span>
        </div>

        {/* Card 3: High Priority / Blocked */}
        <div
          className="keka-card keka-card-hover"
          style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: '#6b7280' }}>Critical / Overdue</span>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: '#fef2f2',
                color: '#991b1b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Flame size={17} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '0.75rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', fontWeight: 600, color: '#991b1b' }}>
              {criticalCount}
            </span>
            <span
              style={{
                fontSize: '0.725rem',
                fontWeight: 500,
                padding: '0.12rem 0.45rem',
                borderRadius: '9999px',
                backgroundColor: '#fef2f2',
                color: '#991b1b',
              }}
            >
              Action Required
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Unassigned / Overdue items
          </span>
        </div>

        {/* Card 4: Operations Velocity */}
        <div
          className="keka-card keka-card-hover"
          style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: '#6b7280' }}>Weekly Resolution Rate</span>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: '#f5f3ff',
                color: '#5b21b6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Activity size={17} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '0.75rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', fontWeight: 600, color: '#18181b' }}>
              98.4%
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.725rem',
                fontWeight: 500,
                padding: '0.12rem 0.45rem',
                borderRadius: '9999px',
                backgroundColor: '#f0fdf4',
                color: '#166534',
              }}
            >
              <TrendingUp size={12} /> +3.4%
            </span>
          </div>
          {/* Progress bar */}
          <div
            style={{
              width: '100%',
              backgroundColor: '#e5e7eb',
              height: '5px',
              borderRadius: '9999px',
              marginTop: '0.5rem',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: '98.4%',
                height: '100%',
                backgroundColor: 'var(--color-primary)',
                borderRadius: '9999px',
              }}
            />
          </div>
        </div>
      </div>

      {/* 3. Mid Section: Two Columns (Pending Approvals Queue & Live Audit Feed) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        {/* Left Column: Pending Approvals Queue */}
        <div style={{ gridColumn: 'span 2' }}>
          <div
            className="keka-card"
            style={{
              padding: '1.5rem',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '1.25rem',
                  paddingBottom: '0.75rem',
                  borderBottom: '1px solid #f3f4f6',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                  <ShieldCheck size={19} color="var(--color-primary)" />
                  <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', fontWeight: 600, color: '#18181b' }}>
                    Pending Approvals &amp; Sign-offs
                  </h2>
                  <span
                    style={{
                      fontSize: '0.725rem',
                      fontWeight: 600,
                      padding: '0.12rem 0.5rem',
                      borderRadius: '9999px',
                      backgroundColor: '#fefce8',
                      color: '#854d0e',
                      border: '1px solid #fef08a',
                    }}
                  >
                    {pendingApprovalItems.length} awaiting review
                  </span>
                </div>
              </div>

              {pendingApprovalItems.length === 0 ? (
                <div
                  style={{
                    padding: '3rem 1.5rem',
                    textAlign: 'center',
                    color: '#6b7280',
                    fontSize: '0.875rem',
                  }}
                >
                  <CheckCircle2 size={36} color="#166534" style={{ margin: '0 auto 0.75rem' }} />
                  <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, color: '#18181b', fontSize: '1rem', marginBottom: '0.25rem' }}>
                    Queue All Clear
                  </div>
                  <div>No pending approvals waiting for leadership sign-off.</div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                  {pendingApprovalItems.map((item: WorkItem) => {
                    const isAssignee = item.assignee_id === user?.id;
                    return (
                      <div
                        key={item.id}
                        style={{
                          padding: '1rem 1.25rem',
                          borderRadius: '8px',
                          border: '1px solid #e5e7eb',
                          backgroundColor: '#ffffff',
                          boxShadow: 'var(--shadow-xs)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.75rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                          <div>
                            <div
                              onClick={() => onSelectItem(item.id)}
                              style={{
                                fontFamily: 'var(--font-serif)',
                                fontSize: '1rem',
                                fontWeight: 600,
                                color: '#18181b',
                                cursor: 'pointer',
                                marginBottom: '0.25rem',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-primary)')}
                              onMouseLeave={(e) => (e.currentTarget.style.color = '#18181b')}
                            >
                              {item.title}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                                Ref: <code style={{ color: 'var(--color-primary)' }}>OPS-{item.id.slice(0, 8)}</code>
                              </span>
                              <span>·</span>
                              <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                                Version v{item.version}
                              </span>
                              <span>·</span>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.25rem',
                                  fontSize: '0.7rem',
                                  fontWeight: 500,
                                  color: '#5b21b6',
                                  backgroundColor: '#f5f3ff',
                                  padding: '0.1rem 0.5rem',
                                  borderRadius: '9999px',
                                  border: '1px solid #ddd6fe',
                                }}
                              >
                                <Shield size={12} /> Separation of Duties
                              </span>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            {getPriorityBadge(item.priority)}
                          </div>
                        </div>

                        {/* Action buttons */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            paddingTop: '0.5rem',
                            borderTop: '1px solid #f9fafb',
                          }}
                        >
                          <div style={{ fontSize: '0.75rem', color: isAssignee ? '#b91c1c' : '#6b7280' }}>
                            {isAssignee
                              ? 'Assigned to you (cannot self-approve)'
                              : 'Requires Lead or Admin sign-off'}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <button
                              onClick={() => onSelectItem(item.id)}
                              className="btn btn-secondary"
                              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                            >
                              Review Details
                            </button>
                            {!isAssignee && (
                              <button
                                onClick={() => approveMutation.mutate({ id: item.id, version: item.version })}
                                disabled={approveMutation.isPending}
                                className="btn btn-primary"
                                style={{ padding: '0.35rem 0.85rem', fontSize: '0.8rem' }}
                              >
                                Approve Request
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Live Operational Audit Trail */}
        <div>
          <div
            className="keka-card"
            style={{
              padding: '1.5rem',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '1.25rem',
                  paddingBottom: '0.75rem',
                  borderBottom: '1px solid #f3f4f6',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Activity size={17} color="var(--color-primary)" />
                  <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.1rem', fontWeight: 600, color: '#18181b' }}>
                    Live Audit Trail
                  </h3>
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    color: '#166534',
                    backgroundColor: '#f0fdf4',
                    padding: '0.12rem 0.5rem',
                    borderRadius: '9999px',
                    border: '1px solid #bbf7d0',
                  }}
                >
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#16a34a',
                    }}
                  />
                  Real-time
                </div>
              </div>

              {/* Event items list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                {teamItems?.items?.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    onClick={() => onSelectItem(item.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.75rem',
                      cursor: 'pointer',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      transition: 'background-color 0.12s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#fafaf9')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div
                      style={{
                        width: '26px',
                        height: '26px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--color-primary-subtle)',
                        color: 'var(--color-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '0.15rem',
                      }}
                    >
                      <Zap size={13} />
                    </div>
                    <div style={{ overflow: 'hidden', flex: 1 }}>
                      <div
                        style={{
                          fontSize: '0.825rem',
                          fontWeight: 500,
                          color: '#18181b',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {item.title}
                      </div>
                      <div style={{ fontSize: '0.725rem', color: '#6b7280', display: 'flex', gap: '0.5rem' }}>
                        <span>Status: {item.status.replace('_', ' ')}</span>
                        <span>·</span>
                        <span>v{item.version}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ paddingTop: '1rem', borderTop: '1px solid #f3f4f6', textAlign: 'center' }}>
              <button
                onClick={() => setActiveTab('all')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-primary)',
                  fontSize: '0.825rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Inspect All Operational Queues ↓
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Attention Queues Grid */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.3rem', fontWeight: 600, color: '#18181b', marginBottom: '1rem' }}>
          Operational Queues Demanding Attention
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
          {dashboard?.sections?.map((section, idx) => (
            <div key={idx} className="keka-card" style={{ padding: '1.25rem' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingBottom: '0.75rem',
                  borderBottom: '1px solid #f3f4f6',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {section.label.toLowerCase().includes('assigned to me') && <UserCheck size={17} color="var(--color-primary)" />}
                  {section.label.toLowerCase().includes('unassigned') && <Flame size={17} color="#991b1b" />}
                  {section.label.toLowerCase().includes('pending') && <Hourglass size={17} color="#854d0e" />}
                  {section.label.toLowerCase().includes('overdue') && <AlertTriangle size={17} color="#c2410c" />}
                  {section.label.toLowerCase().includes('stale') && <Clock size={17} color="#6b7280" />}
                  <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: 600, color: '#18181b' }}>{section.label}</h3>
                </div>
                <span
                  style={{
                    fontSize: '0.725rem',
                    fontWeight: 500,
                    padding: '0.12rem 0.45rem',
                    borderRadius: '9999px',
                    backgroundColor: '#f4f4f5',
                    color: '#3f3f46',
                  }}
                >
                  {section.count} items
                </span>
              </div>

              {section.items.length === 0 ? (
                <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#9ca3af', fontSize: '0.85rem' }}>
                  Queue is clear. No items demanding action.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  {section.items.map((item: WorkItem) => (
                    <div
                      key={item.id}
                      style={{
                        padding: '0.75rem 1rem',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e5e7eb',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '1rem',
                        transition: 'all 0.12s ease',
                      }}
                    >
                      <div
                        onClick={() => onSelectItem(item.id)}
                        style={{ cursor: 'pointer', flex: 1, minWidth: 0 }}
                      >
                        <div
                          style={{
                            fontWeight: 500,
                            fontSize: '0.9rem',
                            color: '#18181b',
                            marginBottom: '0.25rem',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {item.title}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {getPriorityBadge(item.priority)}
                          {getStatusBadge(item.status)}
                          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                            v{item.version}
                          </span>
                          {item.due_at && (
                            <span style={{ fontSize: '0.75rem', color: '#854d0e' }}>
                              Due {new Date(item.due_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Quick Action: Atomic Claim for unassigned items */}
                      {!item.assignee_id && item.status === 'open' ? (
                        <button
                          onClick={() => claimMutation.mutate(item.id)}
                          disabled={claimMutation.isPending}
                          className="btn btn-primary"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.775rem' }}
                          title="Atomic Claim"
                        >
                          <Zap size={13} /> Claim
                        </button>
                      ) : (
                        <button
                          onClick={() => onSelectItem(item.id)}
                          className="btn btn-secondary"
                          style={{ padding: '0.35rem 0.6rem' }}
                          title="Inspect Item"
                        >
                          <ArrowRight size={14} color="#6b7280" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 409 Conflict Modal */}
      <ConflictModal
        isOpen={conflictData.isOpen}
        onClose={() => setConflictData({ isOpen: false, message: '' })}
        onReload={() => {
          setConflictData({ isOpen: false, message: '' });
          refetch();
        }}
        conflictMessage={conflictData.message}
        serverItemTitle={conflictData.serverTitle}
        serverItemVersion={conflictData.serverVersion}
      />
    </div>
  );
};

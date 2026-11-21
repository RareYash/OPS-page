import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserX,
  X,
  XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { ConflictModal } from '../components/ConflictModal';
import { useAuth } from '../context/AuthContext';
import { ItemPriority, WorkItem } from '../types';

interface ApprovalsPageProps {
  onSelectItem: (id: string) => void;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({ onSelectItem }) => {
  const queryClient = useQueryClient();
  const { user, activeTeam } = useAuth();

  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'all' | 'actionable' | 'submitted_by_me'>('all');

  // Reject Modal State
  const [rejectingItem, setRejectingItem] = useState<WorkItem | null>(null);
  const [rejectComment, setRejectComment] = useState('');
  const [rejectError, setRejectError] = useState<string | null>(null);

  // Conflict Modal State
  const [conflictState, setConflictState] = useState<{
    isOpen: boolean;
    message: string;
    serverTitle?: string;
    serverVersion?: number;
  }>({ isOpen: false, message: '' });

  // Fetch pending approval items for current team
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['items', 'pending_approval', activeTeam?.id],
    queryFn: () =>
      api.items.list({
        team_id: activeTeam?.id,
        status: 'pending_approval',
        limit: 100,
      }),
    enabled: !!activeTeam?.id,
    refetchInterval: 15000,
  });

  const items = data?.items || [];

  // Mutations
  const approveMutation = useMutation({
    mutationFn: ({ item }: { item: WorkItem }) =>
      api.items.transition(item.id, 'resolved', item.version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setConflictState({
          isOpen: true,
          message: err.message || 'This work item was modified by another user.',
          serverVersion: err.current_version,
        });
      } else {
        alert(err.message || 'Failed to approve item.');
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ item, comment }: { item: WorkItem; comment: string }) =>
      api.items.transition(item.id, 'in_progress', item.version, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      setRejectingItem(null);
      setRejectComment('');
      setRejectError(null);
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setConflictState({
          isOpen: true,
          message: err.message || 'This work item was modified by another user.',
          serverVersion: err.current_version,
        });
      } else {
        setRejectError(err.message || 'Failed to reject item.');
      }
    },
  });

  const handleOpenReject = (item: WorkItem) => {
    setRejectingItem(item);
    setRejectComment('');
    setRejectError(null);
  };

  const handleConfirmReject = () => {
    if (!rejectComment.trim()) {
      setRejectError('Please provide a reason or corrective instruction for rejection.');
      return;
    }
    if (rejectingItem) {
      rejectMutation.mutate({ item: rejectingItem, comment: rejectComment.trim() });
    }
  };

  // User role checking
  const isLeadOrAdmin = activeTeam?.my_role === 'lead' || activeTeam?.my_role === 'admin';

  // Filters
  const filteredItems = items.filter((item) => {
    // Search
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchDesc = item.description?.toLowerCase().includes(q) ?? false;
      const matchId = item.id.toLowerCase().includes(q);
      if (!matchTitle && !matchDesc && !matchId) return false;
    }
    // Priority
    if (priorityFilter && item.priority !== priorityFilter) {
      return false;
    }
    // Tab
    const isAssignee = item.assignee_id === user?.id;
    if (activeTab === 'actionable') {
      return isLeadOrAdmin && !isAssignee;
    }
    if (activeTab === 'submitted_by_me') {
      return isAssignee;
    }
    return true;
  });

  // Summary counts
  const totalPending = items.length;
  const criticalOrHighCount = items.filter(
    (i) => i.priority === 'critical' || i.priority === 'high'
  ).length;
  const actionableCount = items.filter(
    (i) => isLeadOrAdmin && i.assignee_id !== user?.id
  ).length;
  const mySubmissionsCount = items.filter((i) => i.assignee_id === user?.id).length;

  const renderPriorityBadge = (priority: ItemPriority) => {
    const map: Record<ItemPriority, { bg: string; color: string; border: string }> = {
      critical: { bg: '#fee2e2', color: '#991b1b', border: '#fecaca' },
      high: { bg: '#ffedd5', color: '#9a3412', border: '#fed7aa' },
      medium: { bg: '#fffbeb', color: '#b45309', border: '#fde68a' },
      low: { bg: '#f3f4f6', color: '#374151', border: '#e5e7eb' },
    };
    const c = map[priority] || map.low;
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.25rem',
          fontSize: '0.72rem',
          fontWeight: 600,
          padding: '0.15rem 0.5rem',
          borderRadius: '9999px',
          backgroundColor: c.bg,
          color: c.color,
          border: `1px solid ${c.border}`,
          textTransform: 'capitalize',
        }}
      >
        {priority}
      </span>
    );
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 1. Header Section */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.25rem' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: '#fef3c7',
                color: '#b45309',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <ShieldAlert size={18} />
            </div>
            <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', fontWeight: 600, color: '#18181b', margin: 0 }}>
              Approvals &amp; Sign-Offs
            </h1>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                padding: '0.15rem 0.6rem',
                borderRadius: '9999px',
                backgroundColor: totalPending > 0 ? '#fefce8' : '#f0fdf4',
                color: totalPending > 0 ? '#854d0e' : '#166534',
                border: totalPending > 0 ? '1px solid #fef08a' : '1px solid #bbf7d0',
              }}
            >
              {totalPending} {totalPending === 1 ? 'item' : 'items'} awaiting review
            </span>
          </div>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', margin: 0 }}>
            Four-eyes principle compliance queue for {activeTeam?.name || 'Active Team'} · High-integrity audit sign-offs
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-secondary"
            style={{ height: '36px', fontSize: '0.825rem' }}
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
            <span>Sync Queue</span>
          </button>
        </div>
      </div>

      {/* 2. Key Metrics Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* Metric 1: Pending Queue */}
        <div
          className="keka-card"
          style={{
            padding: '1.15rem 1.25rem',
            borderLeft: '4px solid #f59e0b',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#6b7280' }}>Total Pending Review</span>
            <Clock size={16} color="#f59e0b" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', fontWeight: 700, color: '#18181b' }}>
              {totalPending}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>items in queue</span>
          </div>
        </div>

        {/* Metric 2: Urgent / High Priority */}
        <div
          className="keka-card"
          style={{
            padding: '1.15rem 1.25rem',
            borderLeft: '4px solid #ef4444',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#6b7280' }}>Critical &amp; High Priority</span>
            <AlertTriangle size={16} color="#ef4444" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', fontWeight: 700, color: '#18181b' }}>
              {criticalOrHighCount}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>urgent sign-offs</span>
          </div>
        </div>

        {/* Metric 3: Actionable by Current User */}
        <div
          className="keka-card"
          style={{
            padding: '1.15rem 1.25rem',
            borderLeft: '4px solid var(--color-primary)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#6b7280' }}>Eligible for Your Sign-Off</span>
            <UserCheck size={16} color="var(--color-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', fontWeight: 700, color: '#18181b' }}>
              {isLeadOrAdmin ? actionableCount : 0}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              {isLeadOrAdmin ? 'ready to approve' : 'requires Lead/Admin'}
            </span>
          </div>
        </div>

        {/* Metric 4: Governance Rule Card */}
        <div
          className="keka-card"
          style={{
            padding: '1.15rem 1.25rem',
            borderLeft: '4px solid #10b981',
            backgroundColor: '#f8fafc',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <ShieldCheck size={16} color="#059669" />
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#0f172a' }}>Four-Eyes Principle</span>
          </div>
          <div style={{ fontSize: '0.735rem', color: '#475569', lineHeight: 1.45 }}>
            Strict separation of duties is enforced. Operators cannot approve their own work items. An independent Lead/Admin must sign off.
          </div>
        </div>
      </div>

      {/* 3. Search and Tabs Bar */}
      <div
        className="keka-card"
        style={{
          padding: '0.875rem 1.25rem',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.875rem',
        }}
      >
        {/* Filter Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <button
            onClick={() => setActiveTab('all')}
            className={`keka-tab-btn ${activeTab === 'all' ? 'active' : ''}`}
          >
            All Pending ({totalPending})
          </button>
          <button
            onClick={() => setActiveTab('actionable')}
            className={`keka-tab-btn ${activeTab === 'actionable' ? 'active' : ''}`}
          >
            Ready for My Sign-Off ({isLeadOrAdmin ? actionableCount : 0})
          </button>
          <button
            onClick={() => setActiveTab('submitted_by_me')}
            className={`keka-tab-btn ${activeTab === 'submitted_by_me' ? 'active' : ''}`}
          >
            My Submissions ({mySubmissionsCount})
          </button>
        </div>

        {/* Search & Priority Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: '220px' }}>
            <Search
              size={14}
              color="#6b7280"
              style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Search approvals..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '2.2rem', height: '34px', fontSize: '0.8rem' }}
            />
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="input-field"
            style={{ width: '130px', height: '34px', fontSize: '0.8rem' }}
          >
            <option value="">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* 4. Queue List / Cards */}
      {isLoading ? (
        <div
          className="keka-card"
          style={{
            padding: '3.5rem 1rem',
            textAlign: 'center',
            color: '#6b7280',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              border: '3px solid #e5e7eb',
              borderTopColor: 'var(--color-primary)',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }}
          />
          <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>Loading pending approvals...</div>
        </div>
      ) : isError ? (
        <div
          className="keka-card"
          style={{
            padding: '2.5rem 1rem',
            textAlign: 'center',
            color: '#b91c1c',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
          }}
        >
          <AlertCircle size={32} style={{ margin: '0 auto 0.5rem' }} />
          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Failed to load approvals queue.</div>
          <button
            onClick={() => refetch()}
            className="btn btn-secondary"
            style={{ marginTop: '0.75rem' }}
          >
            Retry
          </button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div
          className="keka-card"
          style={{
            padding: '4rem 1.5rem',
            textAlign: 'center',
            color: '#6b7280',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: '#ecfdf5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
            }}
          >
            <CheckCircle2 size={32} color="#059669" />
          </div>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 600, color: '#18181b', marginBottom: '0.35rem' }}>
            Queue All Clear
          </div>
          <div style={{ maxWidth: '420px', fontSize: '0.875rem', color: '#6b7280', lineHeight: 1.5 }}>
            {searchTerm || priorityFilter || activeTab !== 'all'
              ? 'No pending approvals match your selected search criteria.'
              : 'All submitted work items for this team have been reviewed and approved. No actions are currently waiting in the queue.'}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          {filteredItems.map((item) => {
            const isAssignee = item.assignee_id === user?.id;
            const canApproveItem = isLeadOrAdmin && !isAssignee;
            const isSelfAssigned = isAssignee;

            return (
              <div
                key={item.id}
                className="keka-card"
                style={{
                  padding: '1.25rem 1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1rem',
                  borderLeft:
                    item.priority === 'critical'
                      ? '4px solid #ef4444'
                      : item.priority === 'high'
                      ? '4px solid #f97316'
                      : '4px solid #f59e0b',
                  transition: 'box-shadow 0.15s ease',
                }}
              >
                {/* Top Row: ID, Badges, Due Date */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <span
                      onClick={() => onSelectItem(item.id)}
                      style={{
                        fontFamily: 'monospace',
                        fontWeight: 700,
                        fontSize: '0.85rem',
                        color: 'var(--color-primary)',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                      }}
                    >
                      OPS-{item.id.slice(0, 7)}
                    </span>
                    {renderPriorityBadge(item.priority)}
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '9999px',
                        backgroundColor: '#fefce8',
                        color: '#854d0e',
                        border: '1px solid #fef08a',
                      }}
                    >
                      <Clock size={11} /> Pending Sign-off
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>v{item.version}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.775rem', color: '#6b7280' }}>
                    {item.due_at && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Clock size={13} color="#f97316" />
                        Due: {new Date(item.due_at).toLocaleDateString()}
                      </span>
                    )}
                    <span>Submitted: {new Date(item.updated_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>
                  </div>
                </div>

                {/* Middle: Title & Description */}
                <div>
                  <h3
                    onClick={() => onSelectItem(item.id)}
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      color: '#18181b',
                      margin: '0 0 0.35rem 0',
                      cursor: 'pointer',
                    }}
                  >
                    {item.title}
                  </h3>
                  {item.description && (
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#4b5563', lineHeight: 1.5 }}>
                      {item.description}
                    </p>
                  )}
                </div>

                {/* Separation of Duties Banner if user is the assignee */}
                {isSelfAssigned && (
                  <div
                    style={{
                      padding: '0.625rem 0.875rem',
                      borderRadius: '6px',
                      backgroundColor: '#fffbeb',
                      border: '1px solid #fef3c7',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.625rem',
                      fontSize: '0.785rem',
                      color: '#92400e',
                    }}
                  >
                    <UserX size={15} color="#d97706" />
                    <span>
                      <strong>Separation of duties policy:</strong> You are the author/assignee of this work item.
                      Policy prohibits self-approval. An independent Team Lead or Admin must sign off.
                    </span>
                  </div>
                )}

                {/* Bottom Row: Assignee Info & Actions */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                    paddingTop: '0.75rem',
                    borderTop: '1px solid #f3f4f6',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <div
                      style={{
                        width: '26px',
                        height: '26px',
                        borderRadius: '50%',
                        backgroundColor: '#e0e7ff',
                        color: '#3730a3',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                      }}
                    >
                      {item.assignee_name
                        ? item.assignee_name.split(' ').map((n) => n[0]).join('')
                        : 'U'}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#374151' }}>
                      <span style={{ color: '#6b7280' }}>Operator: </span>
                      <strong style={{ color: '#111827' }}>{item.assignee_name || 'Unassigned'}</strong>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {canApproveItem ? (
                      <>
                        <button
                          onClick={() => handleOpenReject(item)}
                          disabled={rejectMutation.isPending || approveMutation.isPending}
                          className="btn btn-secondary"
                          style={{
                            height: '32px',
                            fontSize: '0.785rem',
                            color: '#b91c1c',
                            borderColor: '#fca5a5',
                          }}
                        >
                          <XCircle size={14} />
                          <span>Reject / Request Changes</span>
                        </button>

                        <button
                          onClick={() => approveMutation.mutate({ item })}
                          disabled={approveMutation.isPending || rejectMutation.isPending}
                          className="btn btn-success"
                          style={{ height: '32px', fontSize: '0.785rem' }}
                        >
                          <CheckCircle size={14} />
                          <span>{approveMutation.isPending ? 'Signing off...' : 'Sign Off & Resolve'}</span>
                        </button>
                      </>
                    ) : !isLeadOrAdmin ? (
                      <span style={{ fontSize: '0.75rem', color: '#6b7280', fontStyle: 'italic' }}>
                        Requires Team Lead or Admin role to approve
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.75rem', color: '#92400e', fontStyle: 'italic' }}>
                        Awaiting independent sign-off
                      </span>
                    )}

                    <button
                      onClick={() => onSelectItem(item.id)}
                      className="btn btn-secondary"
                      style={{ height: '32px', fontSize: '0.785rem' }}
                    >
                      <span>Full Record</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Reject Modal */}
      {rejectingItem && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1rem',
          }}
        >
          <div
            className="keka-card"
            style={{
              width: '100%',
              maxWidth: '480px',
              padding: '1.75rem',
              boxShadow: 'var(--shadow-xl)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    backgroundColor: '#fee2e2',
                    color: '#dc2626',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <XCircle size={18} />
                </div>
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', fontWeight: 600, color: '#18181b', margin: 0 }}>
                  Reject &amp; Send Back to In Progress
                </h3>
              </div>
              <button
                onClick={() => setRejectingItem(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.85rem', color: '#4b5563', margin: '0 0 1rem 0', lineHeight: 1.45 }}>
              Returning <strong>{rejectingItem.title}</strong> to the operator. Please provide constructive feedback or specific deficiencies requiring correction:
            </p>

            <textarea
              className="input-field"
              placeholder="e.g. Unit tests missing edge case for network disconnect; verify database constraint."
              rows={4}
              value={rejectComment}
              onChange={(e) => {
                setRejectComment(e.target.value);
                setRejectError(null);
              }}
              style={{ width: '100%', resize: 'vertical', fontSize: '0.85rem', marginBottom: '0.75rem' }}
            />

            {rejectError && (
              <div style={{ fontSize: '0.785rem', color: '#dc2626', marginBottom: '0.75rem' }}>
                {rejectError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.625rem' }}>
              <button
                onClick={() => setRejectingItem(null)}
                className="btn btn-secondary"
                disabled={rejectMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="btn btn-danger"
                disabled={rejectMutation.isPending}
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Optimistic Concurrency Conflict Modal */}
      <ConflictModal
        isOpen={conflictState.isOpen}
        onClose={() => setConflictState({ isOpen: false, message: '' })}
        onReload={() => {
          setConflictState({ isOpen: false, message: '' });
          refetch();
        }}
        conflictMessage={conflictState.message}
        serverItemVersion={conflictState.serverVersion}
      />
    </div>
  );
};

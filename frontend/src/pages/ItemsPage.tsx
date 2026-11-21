import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight,
  Filter,
  Key,
  Layers,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  SlidersHorizontal,
  X,
  Zap,
} from 'lucide-react';
import { api, generateUUID } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ItemPriority, ItemStatus, WorkItem } from '../types';

interface ItemsPageProps {
  onSelectItem: (id: string) => void;
}

export const ItemsPage: React.FC<ItemsPageProps> = ({ onSelectItem }) => {
  const queryClient = useQueryClient();
  const { user, activeTeam } = useAuth();

  // Search & Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [cursor, setCursor] = useState<string | null>(null);

  // Accumulated items for "Load More" cursor pagination
  const [accumulatedItems, setAccumulatedItems] = useState<WorkItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  // Create Item Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState<string>('');
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPriority, setNewPriority] = useState<ItemPriority>('medium');
  const [newRequiresApproval, setNewRequiresApproval] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Reset pagination when filters or search change
  useEffect(() => {
    setCursor(null);
    setAccumulatedItems([]);
  }, [activeTeam?.id, debouncedSearch, statusFilter, priorityFilter]);

  // Query items
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: [
      'items',
      activeTeam?.id,
      debouncedSearch,
      statusFilter,
      priorityFilter,
      cursor,
    ],
    queryFn: () =>
      api.items.list({
        team_id: activeTeam?.id,
        q: debouncedSearch || undefined,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        cursor: cursor || undefined,
        limit: 20,
      }),
    enabled: !!activeTeam,
  });

  // Accumulate pages when cursor pagination returns data
  useEffect(() => {
    if (data?.items) {
      if (!cursor) {
        setAccumulatedItems(data.items);
      } else {
        setAccumulatedItems((prev) => [...prev, ...data.items]);
      }
      setNextCursor(data.next_cursor);
    }
  }, [data, cursor]);

  // Create Item Mutation with Idempotency
  const createMutation = useMutation({
    mutationFn: (payload: {
      team_id: string;
      title: string;
      description?: string;
      priority: string;
      requires_approval: boolean;
    }) => api.items.create(payload, idempotencyKey),
    onSuccess: (createdItem) => {
      setIsCreateOpen(false);
      setNewTitle('');
      setNewDesc('');
      setNewPriority('medium');
      setNewRequiresApproval(false);
      setCreateError(null);
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onSelectItem(createdItem.id);
    },
    onError: (err: any) => {
      setCreateError(err?.message || 'Failed to create item');
    },
  });

  const handleOpenCreateModal = () => {
    setIdempotencyKey(generateUUID());
    setCreateError(null);
    setIsCreateOpen(true);
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTeam) return;
    if (!newTitle.trim()) {
      setCreateError('Title is required');
      return;
    }
    createMutation.mutate({
      team_id: activeTeam.id,
      title: newTitle.trim(),
      description: newDesc.trim() || undefined,
      priority: newPriority,
      requires_approval: newRequiresApproval,
    });
  };

  const handleLoadMore = () => {
    if (nextCursor) {
      setCursor(nextCursor);
    }
  };

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

  return (
    <div className="app-container animate-fade-in" style={{ maxWidth: '1440px', paddingBottom: '3rem' }}>
      {/* Top Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.85rem', fontWeight: 600, color: '#18181b', marginBottom: '0.25rem' }}>
            Work Items Registry
          </h1>
          <p style={{ color: '#6b7280', fontSize: '0.85rem' }}>
            Keyset-paginated high-concurrency registry for <strong>{activeTeam?.name}</strong>
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={() => refetch()}
            className="btn btn-secondary"
            title="Refresh List"
          >
            <RefreshCw size={14} className={isFetching ? 'spin-slow' : ''} />
            <span>Sync</span>
          </button>
          <button
            onClick={handleOpenCreateModal}
            className="btn btn-primary"
            title="Create Work Item with Idempotency Key"
          >
            <Plus size={15} />
            <span>New Work Item</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div
        className="keka-card"
        style={{
          padding: '0.875rem 1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
        }}
      >
        {/* Quick status tabs */}
        <div style={{ display: 'flex', gap: '0.25rem', overflowX: 'auto' }}>
          <button
            onClick={() => setStatusFilter('')}
            className={`keka-tab-btn ${statusFilter === '' ? 'active' : ''}`}
          >
            All Items
          </button>
          <button
            onClick={() => setStatusFilter('open')}
            className={`keka-tab-btn ${statusFilter === 'open' ? 'active' : ''}`}
          >
            Open
          </button>
          <button
            onClick={() => setStatusFilter('in_progress')}
            className={`keka-tab-btn ${statusFilter === 'in_progress' ? 'active' : ''}`}
          >
            In Progress
          </button>
          <button
            onClick={() => setStatusFilter('pending_approval')}
            className={`keka-tab-btn ${statusFilter === 'pending_approval' ? 'active' : ''}`}
          >
            Pending Approval
          </button>
          <button
            onClick={() => setStatusFilter('resolved')}
            className={`keka-tab-btn ${statusFilter === 'resolved' ? 'active' : ''}`}
          >
            Resolved
          </button>
        </div>

        {/* Search & Priority Select */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: '250px' }}>
            <Search
              size={14}
              color="#6b7280"
              style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Search items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '2.2rem', paddingRight: '2rem', height: '35px' }}
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                style={{
                  position: 'absolute',
                  right: '0.65rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#9ca3af',
                  cursor: 'pointer',
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <SlidersHorizontal size={14} color="#6b7280" />
            <select
              className="input-field"
              style={{ width: 'auto', padding: '0.35rem 0.75rem', height: '35px' }}
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
            >
              <option value="">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Items Table Container */}
      <div className="keka-card" style={{ overflow: 'hidden' }}>
        {isLoading && accumulatedItems.length === 0 ? (
          <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--color-primary)', fontFamily: 'var(--font-serif)', fontSize: '1rem' }}>
            Retrieving indexed records...
          </div>
        ) : accumulatedItems.length === 0 ? (
          <div style={{ padding: '4rem 2rem', textAlign: 'center' }}>
            <div style={{ fontFamily: 'var(--font-serif)', color: '#18181b', fontWeight: 600, fontSize: '1.15rem', marginBottom: '0.5rem' }}>
              No work items found
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              Try adjusting your search criteria or clear active status filters.
            </div>
            <button
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('');
                setPriorityFilter('');
              }}
              className="btn btn-secondary"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="keka-table">
              <thead>
                <tr>
                  <th style={{ width: '120px' }}>Item ID</th>
                  <th>Work Item Title &amp; Description</th>
                  <th style={{ width: '130px' }}>Priority</th>
                  <th style={{ width: '150px' }}>Status</th>
                  <th style={{ width: '160px' }}>Assignee</th>
                  <th style={{ width: '90px' }}>Version</th>
                  <th style={{ width: '60px', textAlign: 'right' }}></th>
                </tr>
              </thead>
              <tbody>
                {accumulatedItems.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => onSelectItem(item.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-primary)', fontWeight: 600 }}>
                        OPS-{item.id.slice(0, 6)}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '0.95rem', color: '#18181b', marginBottom: '0.2rem' }}>
                        {item.title}
                      </div>
                      {item.description && (
                        <div
                          style={{
                            fontSize: '0.775rem',
                            color: '#6b7280',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            maxWidth: '460px',
                          }}
                        >
                          {item.description}
                        </div>
                      )}
                    </td>
                    <td>{getPriorityBadge(item.priority)}</td>
                    <td>{getStatusBadge(item.status)}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div
                          style={{
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            backgroundColor: item.assignee_name ? 'var(--color-primary-subtle)' : '#f4f4f5',
                            color: item.assignee_name ? 'var(--color-primary)' : '#9ca3af',
                            fontSize: '0.65rem',
                            fontWeight: 600,
                            fontFamily: 'var(--font-serif)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {item.assignee_name ? item.assignee_name.split(' ').map((n) => n[0]).join('') : '?'}
                        </div>
                        <span style={{ fontSize: '0.825rem', color: item.assignee_name ? '#18181b' : '#9ca3af' }}>
                          {item.assignee_name || 'Unassigned'}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#6b7280' }}>
                        v{item.version}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', color: '#9ca3af' }}>
                      <ChevronRight size={16} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Keyset Cursor Load More Button */}
        {nextCursor && (
          <div style={{ padding: '1.25rem', textAlign: 'center', borderTop: '1px solid #e5e7eb' }}>
            <button
              onClick={handleLoadMore}
              disabled={isFetching}
              className="btn btn-secondary"
              style={{ width: '240px' }}
            >
              {isFetching ? 'Loading next page...' : 'Load More Items (Cursor)'}
            </button>
          </div>
        )}
      </div>

      {/* Create Work Item Modal */}
      {isCreateOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.4)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999,
            padding: '1rem',
          }}
        >
          <div
            className="keka-card animate-fade-in"
            style={{ width: '100%', maxWidth: '540px', padding: '2rem', boxShadow: 'var(--shadow-xl)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
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
                  <Plus size={17} />
                </div>
                <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 600, color: '#18181b' }}>
                  Create Work Item
                </h3>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Idempotency Key Notice */}
            <div
              style={{
                fontSize: '0.725rem',
                color: '#6b7280',
                background: '#f9fafb',
                padding: '0.6rem 0.85rem',
                borderRadius: '6px',
                border: '1px solid #e5e7eb',
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <Key size={14} color="var(--color-primary)" />
              <span>
                Idempotency Key: <code style={{ color: 'var(--color-primary)' }}>{idempotencyKey.slice(0, 16)}...</code> (Safe from double-clicks)
              </span>
            </div>

            {createError && (
              <div
                style={{
                  padding: '0.75rem',
                  borderRadius: '6px',
                  backgroundColor: '#fef2f2',
                  border: '1px solid #fecaca',
                  color: '#b91c1c',
                  fontSize: '0.825rem',
                  marginBottom: '1rem',
                }}
              >
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#374151', marginBottom: '0.35rem' }}>
                  Title <span style={{ color: '#b91c1c' }}>*</span>
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. SRE: Implement automated offboarding de-provisioning hook"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  autoFocus
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#374151', marginBottom: '0.35rem' }}>
                  Description (Optional)
                </label>
                <textarea
                  className="input-field"
                  rows={3}
                  placeholder="Context, objectives, dependencies..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{ resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#374151', marginBottom: '0.35rem' }}>
                    Priority
                  </label>
                  <select
                    className="input-field"
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as ItemPriority)}
                  >
                    <option value="low">Low (P3)</option>
                    <option value="medium">Medium (P2)</option>
                    <option value="high">High (P1)</option>
                    <option value="critical">Critical (P0)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#374151', marginBottom: '0.35rem' }}>
                    Approval Policy
                  </label>
                  <div
                    onClick={() => setNewRequiresApproval(!newRequiresApproval)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      height: '36px',
                      cursor: 'pointer',
                      padding: '0 0.5rem',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={newRequiresApproval}
                      onChange={(e) => setNewRequiresApproval(e.target.checked)}
                      style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                    />
                    <span style={{ fontSize: '0.825rem', color: '#18181b' }}>
                      Requires Lead Sign-off
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="btn btn-primary"
                >
                  {createMutation.isPending ? 'Publishing...' : 'Create Item'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

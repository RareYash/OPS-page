import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle,
  CheckCircle2,
  Clock,
  Edit3,
  History,
  MessageSquare,
  Play,
  RotateCcw,
  Save,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  User,
  UserCheck,
  UserPlus,
  UserX,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { api } from '../api/client';
import { ConflictModal } from '../components/ConflictModal';
import { useAuth } from '../context/AuthContext';
import { ItemPriority, ItemStatus, Role, WorkItem } from '../types';

interface ItemDetailPageProps {
  itemId: string;
  onBack: () => void;
}

export const ItemDetailPage: React.FC<ItemDetailPageProps> = ({ itemId, onBack }) => {
  const queryClient = useQueryClient();
  const { user, activeTeam } = useAuth();

  // Local editable draft state
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [draftDescription, setDraftDescription] = useState('');
  const [draftPriority, setDraftPriority] = useState<ItemPriority>('medium');
  const [staleBanner, setStaleBanner] = useState<string | null>(null);

  // Rejection modal state (comment required)
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [rejectComment, setRejectComment] = useState('');

  // Comment input
  const [commentBody, setCommentBody] = useState('');

  // Conflict modal state
  const [conflictData, setConflictData] = useState<{
    isOpen: boolean;
    message: string;
    serverTitle?: string;
    serverVersion?: number;
  }>({
    isOpen: false,
    message: '',
  });

  // Query item with 10s background polling
  const {
    data: item,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['item', itemId],
    queryFn: () => api.items.get(itemId),
    refetchInterval: 10000,
  });

  // Query comments
  const { data: comments, refetch: refetchComments } = useQuery({
    queryKey: ['comments', itemId],
    queryFn: () => api.items.getComments(itemId),
    refetchInterval: 10000,
  });

  // Query audit events
  const { data: eventsData, refetch: refetchEvents } = useQuery({
    queryKey: ['events', itemId],
    queryFn: () => api.items.getEvents(itemId),
    refetchInterval: 15000,
  });

  // Sync draft when item loads first time
  useEffect(() => {
    if (item && !isEditing) {
      setDraftTitle(item.title);
      setDraftDescription(item.description || '');
      setDraftPriority(item.priority);
    } else if (item && isEditing) {
      if (item.title !== draftTitle || (item.description || '') !== draftDescription) {
        setStaleBanner(`A newer version (v${item.version}) was committed by another operator.`);
      }
    }
  }, [item]);

  // Handle generic 409 conflict
  const handleMutationError = (err: any) => {
    if (err.status === 409) {
      setConflictData({
        isOpen: true,
        message: err.message || 'Concurrency conflict: record has been updated by someone else.',
        serverTitle: err.currentData?.title,
        serverVersion: err.currentData?.version,
      });
    }
    refetch();
  };

  // Optimistic Update Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { title: string; description: string; priority: ItemPriority }) =>
      api.items.update(itemId, payload, item!.version),
    onSuccess: (updated) => {
      setIsEditing(false);
      setStaleBanner(null);
      queryClient.setQueryData(['item', itemId], updated);
      queryClient.invalidateQueries({ queryKey: ['events', itemId] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
    onError: handleMutationError,
  });

  // Claim Mutation
  const claimMutation = useMutation({
    mutationFn: () => api.items.claim(itemId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['item', itemId], updated);
      queryClient.invalidateQueries({ queryKey: ['events', itemId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
    onError: handleMutationError,
  });

  // Release Mutation
  const releaseMutation = useMutation({
    mutationFn: () => api.items.release(itemId, item!.version),
    onSuccess: (updated) => {
      queryClient.setQueryData(['item', itemId], updated);
      queryClient.invalidateQueries({ queryKey: ['events', itemId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: handleMutationError,
  });

  // Transition Mutation
  const transitionMutation = useMutation({
    mutationFn: ({ to, comment }: { to: string; comment?: string }) =>
      api.items.transition(itemId, to, item!.version, comment),
    onSuccess: (updated) => {
      setIsRejectModalOpen(false);
      setRejectComment('');
      queryClient.setQueryData(['item', itemId], updated);
      queryClient.invalidateQueries({ queryKey: ['events', itemId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: handleMutationError,
  });

  // Comment Mutation with Optimistic Insertion
  const commentMutation = useMutation({
    mutationFn: (body: string) => api.items.addComment(itemId, body),
    onMutate: async (newCommentText) => {
      await queryClient.cancelQueries({ queryKey: ['comments', itemId] });
      const previousComments = queryClient.getQueryData(['comments', itemId]);

      const optimisticComment = {
        id: 'temp-' + Date.now(),
        item_id: itemId,
        author_id: user?.id || '',
        author_name: user?.name || 'You',
        body: newCommentText,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData(['comments', itemId], (old: any) =>
        old ? [...old, optimisticComment] : [optimisticComment]
      );

      return { previousComments };
    },
    onError: (err, _newComment, context) => {
      if (context?.previousComments) {
        queryClient.setQueryData(['comments', itemId], context.previousComments);
      }
      handleMutationError(err);
    },
    onSettled: () => {
      refetchComments();
      refetchEvents();
    },
  });

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draftTitle.trim() || !item) return;
    updateMutation.mutate({
      title: draftTitle.trim(),
      description: draftDescription.trim(),
      priority: draftPriority,
    });
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentBody.trim()) return;
    const body = commentBody.trim();
    setCommentBody('');
    commentMutation.mutate(body);
  };

  const handleConfirmReject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectComment.trim()) return;
    transitionMutation.mutate({ to: 'in_progress', comment: rejectComment.trim() });
  };

  if (isLoading) {
    return (
      <div className="app-container" style={{ padding: '4rem 1.5rem', textAlign: 'center', color: 'var(--color-primary)', fontFamily: 'var(--font-serif)', fontSize: '1.1rem' }}>
        Retrieving item dossier...
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="app-container" style={{ padding: '2rem 1.5rem' }}>
        <button onClick={onBack} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          <ArrowLeft size={15} /> Return to Work Items
        </button>
        <div className="keka-card" style={{ padding: '2.5rem', textAlign: 'center', borderColor: '#fecaca' }}>
          <AlertCircle size={40} color="#b91c1c" style={{ margin: '0 auto 1rem' }} />
          <h2 style={{ fontFamily: 'var(--font-serif)', color: '#18181b' }}>Item Not Found or Access Denied</h2>
          <p style={{ color: '#6b7280', marginTop: '0.5rem' }}>
            Outsider resource isolation guarantees 404 Not Found for non-team members.
          </p>
        </div>
      </div>
    );
  }

  const allowedActions = item.allowed_actions || [];
  const isAssignee = item.assignee_id === user?.id;
  const isPendingApproval = item.status === 'pending_approval';
  const isSeparationOfDutiesConflict = isAssignee && isPendingApproval;

  const statuses: ItemStatus[] = ['open', 'in_progress', 'pending_approval', 'resolved', 'closed'];
  const currentStatusIndex = statuses.indexOf(item.status);

  return (
    <div className="app-container animate-fade-in" style={{ maxWidth: '1440px', paddingBottom: '4rem' }}>
      {/* Top Breadcrumb & Status Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button onClick={onBack} className="btn btn-secondary" style={{ height: '35px', padding: '0 0.75rem' }}>
            <ArrowLeft size={14} /> Back to Registry
          </button>
          <span style={{ color: '#d1d5db' }}>/</span>
          <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
            Work Item <code style={{ color: 'var(--color-primary)', fontWeight: 600 }}>OPS-{item.id.slice(0, 8)}</code>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span
            style={{
              fontSize: '0.75rem',
              color: '#6b7280',
              backgroundColor: '#f4f4f5',
              padding: '0.2rem 0.6rem',
              borderRadius: '4px',
              fontFamily: 'var(--font-mono)',
            }}
          >
            Optimistic Version: <strong>v{item.version}</strong>
          </span>
          <button onClick={() => refetch()} className="btn btn-secondary" style={{ height: '35px', padding: '0 0.75rem' }}>
            <RotateCcw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Stale Concurrency Warning */}
      {staleBanner && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 1rem',
            background: '#fefce8',
            border: '1px solid #fef08a',
            borderRadius: '6px',
            color: '#854d0e',
            marginBottom: '1.25rem',
            fontSize: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={18} color="#c2410c" />
            <span>{staleBanner} Your local draft is preserved.</span>
          </div>
          <button
            onClick={() => {
              setDraftTitle(item.title);
              setDraftDescription(item.description || '');
              setDraftPriority(item.priority);
              setStaleBanner(null);
            }}
            className="btn btn-secondary"
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
          >
            Overwrite with Server Version
          </button>
        </div>
      )}

      {/* Separation of Duties Warning */}
      {isSeparationOfDutiesConflict && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.875rem 1.25rem',
            background: '#f5f3ff',
            border: '1px solid #ddd6fe',
            borderRadius: '6px',
            color: '#5b21b6',
            marginBottom: '1.25rem',
            fontSize: '0.875rem',
          }}
        >
          <ShieldAlert size={20} color="#7c3aed" />
          <div>
            <strong>Separation of Duties Enforced:</strong> You are the assigned engineer for this work item.
            Backend policy strictly prohibits self-approval. An independent Team Lead or Admin must approve or reject.
          </div>
        </div>
      )}

      {/* Workflow Stepper Bar */}
      <div
        className="keka-card"
        style={{
          padding: '1rem 1.5rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          overflowX: 'auto',
          gap: '1rem',
        }}
      >
        {statuses.map((s, idx) => {
          const isDone = idx < currentStatusIndex;
          const isCurrent = idx === currentStatusIndex;
          return (
            <React.Fragment key={s}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: isCurrent ? 'var(--color-primary)' : isDone ? '#166534' : '#e5e7eb',
                    color: isCurrent || isDone ? '#ffffff' : '#6b7280',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.725rem',
                    fontWeight: 600,
                  }}
                >
                  {isDone ? <Check size={14} /> : idx + 1}
                </div>
                <span
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: isCurrent ? 600 : 500,
                    color: isCurrent ? 'var(--color-primary)' : isDone ? '#18181b' : '#9ca3af',
                    textTransform: 'capitalize',
                  }}
                >
                  {s.replace('_', ' ')}
                </span>
              </div>
              {idx < statuses.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: '2px',
                    backgroundColor: idx < currentStatusIndex ? '#166534' : '#e5e7eb',
                    minWidth: '24px',
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Main Grid: Details (Left 65%) + Timeline & Comments (Right 35%) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
        {/* Left Column: Details & Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', gridColumn: 'span 2' }}>
          {/* Card: Item Details */}
          <div className="keka-card" style={{ padding: '1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span className={`badge badge-${item.priority}`}>{item.priority}</span>
                <span className={`badge badge-${item.status}`}>{item.status.replace('_', ' ')}</span>
                {item.requires_approval && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      fontSize: '0.725rem',
                      fontWeight: 500,
                      padding: '0.12rem 0.45rem',
                      borderRadius: '9999px',
                      backgroundColor: '#f5f3ff',
                      color: '#5b21b6',
                      border: '1px solid #ddd6fe',
                    }}
                  >
                    <Shield size={12} /> Lead Sign-Off Required
                  </span>
                )}
              </div>
              {allowedActions.includes('edit') && !isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="btn btn-secondary"
                  style={{ height: '32px', padding: '0 0.75rem', fontSize: '0.8rem' }}
                >
                  <Edit3 size={14} /> Edit
                </button>
              )}
            </div>

            {isEditing ? (
              <form onSubmit={handleSaveEdit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#6b7280', marginBottom: '0.35rem' }}>
                    TITLE
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#6b7280', marginBottom: '0.35rem' }}>
                    DESCRIPTION
                  </label>
                  <textarea
                    className="input-field"
                    rows={6}
                    value={draftDescription}
                    onChange={(e) => setDraftDescription(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#6b7280', marginBottom: '0.35rem' }}>
                    PRIORITY
                  </label>
                  <select
                    className="input-field"
                    value={draftPriority}
                    onChange={(e) => setDraftPriority(e.target.value as ItemPriority)}
                    style={{ width: '200px' }}
                  >
                    <option value="low">Low (P3)</option>
                    <option value="medium">Medium (P2)</option>
                    <option value="high">High (P1)</option>
                    <option value="critical">Critical (P0)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false);
                      setDraftTitle(item.title);
                      setDraftDescription(item.description || '');
                    }}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updateMutation.isPending}
                    className="btn btn-primary"
                  >
                    <Save size={14} /> Save Changes
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.6rem', fontWeight: 600, color: '#18181b', marginBottom: '0.75rem', lineHeight: 1.35 }}>
                  {item.title}
                </h1>
                <div style={{ fontSize: '0.925rem', color: '#4b5563', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
                  {item.description || <em style={{ color: '#9ca3af' }}>No description provided.</em>}
                </div>
              </div>
            )}

            {/* Properties Metadata */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '1.25rem',
                borderTop: '1px solid #f3f4f6',
                marginTop: '1.75rem',
                paddingTop: '1.25rem',
                fontSize: '0.8rem',
              }}
            >
              <div>
                <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Assignee</div>
                <div style={{ fontWeight: 500, color: '#18181b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <User size={14} color="var(--color-primary)" />
                  {item.assignee_name || <em>Unassigned</em>}
                </div>
              </div>
              <div>
                <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Created By</div>
                <div style={{ fontWeight: 500, color: '#18181b' }}>{item.creator_name || 'System Operator'}</div>
              </div>
              <div>
                <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Created At</div>
                <div style={{ color: '#18181b' }}>{new Date(item.created_at).toLocaleDateString()}</div>
              </div>
              <div>
                <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Last Mutated</div>
                <div style={{ color: '#18181b' }}>{new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
              </div>
            </div>
          </div>

          {/* Workflow Action Bar */}
          <div className="keka-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: 600, color: '#18181b', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap size={16} color="var(--color-primary)" /> Workflow &amp; Operational Actions
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
              {/* Claim Action */}
              {allowedActions.includes('claim') && (
                <button
                  onClick={() => claimMutation.mutate()}
                  disabled={claimMutation.isPending}
                  className="btn btn-primary"
                >
                  <Zap size={14} /> Claim This Work (Atomic)
                </button>
              )}

              {/* Release Action */}
              {allowedActions.includes('release') && (
                <button
                  onClick={() => releaseMutation.mutate()}
                  disabled={releaseMutation.isPending}
                  className="btn btn-secondary"
                >
                  <UserX size={14} /> Release (Unassign)
                </button>
              )}

              {/* Start Work: open -> in_progress */}
              {allowedActions.includes('transition:in_progress') && item.status === 'open' && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'in_progress' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-primary"
                >
                  <Play size={14} /> Start Work
                </button>
              )}

              {/* Submit for Approval: in_progress -> pending_approval */}
              {allowedActions.includes('transition:pending_approval') && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'pending_approval' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-accent"
                >
                  <Clock size={14} /> Submit for Approval
                </button>
              )}

              {/* Approve: pending_approval -> resolved */}
              {allowedActions.includes('transition:resolved') && item.status === 'pending_approval' && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'resolved' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-success"
                >
                  <CheckCircle size={14} /> Approve &amp; Mark Resolved
                </button>
              )}

              {/* Reject: pending_approval -> in_progress (requires comment) */}
              {allowedActions.includes('transition:in_progress') && item.status === 'pending_approval' && (
                <button
                  onClick={() => setIsRejectModalOpen(true)}
                  disabled={transitionMutation.isPending}
                  className="btn btn-danger"
                >
                  <XCircle size={14} /> Reject (Send Back)
                </button>
              )}

              {/* Resolve: in_progress -> resolved */}
              {allowedActions.includes('transition:resolved') && item.status === 'in_progress' && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'resolved' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-success"
                >
                  <CheckCircle2 size={14} /> Mark Resolved
                </button>
              )}

              {/* Reopen: resolved -> open */}
              {allowedActions.includes('transition:open') && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'open' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-secondary"
                >
                  <RotateCcw size={14} /> Reopen Item
                </button>
              )}

              {/* Close: resolved -> closed */}
              {allowedActions.includes('transition:closed') && (
                <button
                  onClick={() => transitionMutation.mutate({ to: 'closed' })}
                  disabled={transitionMutation.isPending}
                  className="btn btn-secondary"
                >
                  <CheckCircle2 size={14} /> Close Permanently
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Comments & Audit Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Comments Panel */}
          <div className="keka-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: 600, color: '#18181b', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={16} color="var(--color-primary)" /> Team Discussion
            </h3>

            {/* Comment List */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                maxHeight: '280px',
                overflowY: 'auto',
                marginBottom: '1rem',
              }}
            >
              {!comments?.length ? (
                <div style={{ color: '#9ca3af', fontSize: '0.825rem', textAlign: 'center', padding: '1rem' }}>
                  No comments yet. Post an operational update below.
                </div>
              ) : (
                comments.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      background: '#fafaf9',
                      padding: '0.75rem',
                      borderRadius: '6px',
                      border: '1px solid #e5e7eb',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <strong style={{ fontSize: '0.8rem', color: '#18181b' }}>
                        {c.author_name || 'Operator'}
                      </strong>
                      <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                        {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.825rem', color: '#4b5563', lineHeight: 1.5 }}>
                      {c.body}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add Comment Input */}
            <form onSubmit={handleAddComment} style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                className="input-field"
                placeholder="Post operational update..."
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
              />
              <button
                type="submit"
                disabled={commentMutation.isPending || !commentBody.trim()}
                className="btn btn-primary"
                style={{ padding: '0.5rem 0.85rem' }}
              >
                <Send size={14} />
              </button>
            </form>
          </div>

          {/* Immutable Audit Log Timeline */}
          <div className="keka-card" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', fontWeight: 600, color: '#18181b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <History size={16} color="#166534" /> Immutable Audit Trail
              </h3>
              <span style={{ fontSize: '0.7rem', color: '#166534', backgroundColor: '#f0fdf4', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
                TRIGGER PROTECTED
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
              {!eventsData?.events?.length ? (
                <div style={{ color: '#9ca3af', fontSize: '0.825rem', textAlign: 'center', padding: '1rem' }}>
                  No events recorded.
                </div>
              ) : (
                eventsData.events.map((evt) => (
                  <div
                    key={evt.id}
                    style={{
                      borderLeft: '2px solid var(--color-primary)',
                      paddingLeft: '0.75rem',
                      fontSize: '0.8rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, color: 'var(--color-primary)', textTransform: 'uppercase', fontSize: '0.7rem' }}>
                        {evt.type}
                      </span>
                      <span style={{ color: '#6b7280', fontSize: '0.7rem' }}>
                        {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div style={{ color: '#18181b', marginTop: '0.15rem' }}>
                      Actor: <strong>{evt.actor_name || 'Operator'}</strong>
                    </div>
                    {evt.payload && (
                      <div
                        style={{
                          fontSize: '0.725rem',
                          color: '#6b7280',
                          marginTop: '0.2rem',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {JSON.stringify(evt.payload)}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Rejection Modal (Comment Required) */}
      {isRejectModalOpen && (
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
          <div className="keka-card animate-fade-in" style={{ width: '100%', maxWidth: '480px', padding: '2rem', boxShadow: 'var(--shadow-xl)' }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: '#b91c1c' }}>
              Rejection Notice Required
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1rem' }}>
              Workflow rules mandate an explanatory comment when rejecting an item and returning it to in progress.
            </p>

            <form onSubmit={handleConfirmReject} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <textarea
                className="input-field"
                rows={4}
                placeholder="Explain required changes, missing tests, or failure reasons..."
                value={rejectComment}
                onChange={(e) => setRejectComment(e.target.value)}
                required
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setIsRejectModalOpen(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={transitionMutation.isPending || !rejectComment.trim()}
                  className="btn btn-danger"
                >
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 409 Conflict Resolution Modal */}
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

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Bell,
  CheckCircle2,
  ChevronDown,
  Layers,
  LayoutDashboard,
  LogOut,
  Plus,
  Search,
  Shield,
  ShieldAlert,
  User as UserIcon,
  Users,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Role } from '../types';
import { Logo } from './Logo';

interface NavbarProps {
  currentView: 'dashboard' | 'items' | 'approvals' | 'detail';
  setCurrentView: (view: 'dashboard' | 'items' | 'approvals' | 'detail') => void;
  selectedItemId: string | null;
  onOpenCreateItem?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentView,
  setCurrentView,
  onOpenCreateItem,
}) => {
  const { user, teams, activeTeam, setActiveTeam, logout } = useAuth();
  const [showTeamMenu, setShowTeamMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  // Fetch notifications with polling
  const { data: notifData, refetch: refetchNotifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.notifications.list(),
    refetchInterval: 15000,
    enabled: !!user,
  });

  // Query dashboard for counts
  const { data: dashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.dashboard.get(),
    refetchInterval: 30000,
    enabled: !!user,
  });

  const unreadCount = notifData?.unread_count || 0;
  const pendingApprovalsCount = dashboard?.status_counts?.['pending_approval'] || 0;
  const openCount = (dashboard?.status_counts?.['open'] || 0) + (dashboard?.status_counts?.['in_progress'] || 0);

  const handleMarkRead = async (id: string) => {
    try {
      await api.notifications.markRead(id);
      refetchNotifs();
    } catch {
      // Ignore
    }
  };

  const getRoleBadgeClass = (role?: Role) => {
    switch (role) {
      case 'admin':
        return 'badge-admin';
      case 'lead':
        return 'badge-lead';
      case 'member':
        return 'badge-member';
      default:
        return 'badge-viewer';
    }
  };

  return (
    <>
      {/* 1. Left Sidebar Anchor (Matte Slate / Charcoal Navigation Shell) */}
      <aside
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          width: '250px',
          backgroundColor: 'var(--sidebar-bg)',
          borderRight: '1px solid var(--sidebar-border)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '1.25rem 1rem',
          zIndex: 60,
          boxShadow: '1px 0 3px rgba(0, 0, 0, 0.05)',
        }}
        className="keka-sidebar"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {/* Logo / Brand with Noto Serif */}
          <div
            onClick={() => setCurrentView('dashboard')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              cursor: 'pointer',
              padding: '0.25rem 0.5rem',
            }}
          >
            <Logo size={34} showShadow={false} />
            <div>
              <div
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: '1.15rem',
                  fontWeight: 700,
                  color: '#ffffff',
                  letterSpacing: '-0.02em',
                }}
              >
                Y corp. <span style={{ color: '#f97316', fontSize: '0.85rem', fontWeight: 600 }}>Ops</span>
              </div>
              <div
                style={{
                  fontSize: '0.625rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: '#a8a29e',
                  fontWeight: 500,
                }}
              >
                Operations Management
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {/* Dashboard */}
            <div
              onClick={() => setCurrentView('dashboard')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.6rem 0.85rem',
                borderRadius: '6px',
                cursor: 'pointer',
                background: currentView === 'dashboard' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                color: currentView === 'dashboard' ? '#ffffff' : '#a8a29e',
                borderLeft: currentView === 'dashboard' ? '3px solid #ea580c' : '3px solid transparent',
                fontWeight: currentView === 'dashboard' ? 600 : 500,
                fontSize: '0.875rem',
                transition: 'all 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (currentView !== 'dashboard') {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.color = '#ffffff';
                }
              }}
              onMouseLeave={(e) => {
                if (currentView !== 'dashboard') {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#a8a29e';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <LayoutDashboard size={17} />
                <span>Dashboard</span>
              </div>
            </div>

            {/* Work Items */}
            <div
              onClick={() => setCurrentView('items')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.6rem 0.85rem',
                borderRadius: '6px',
                cursor: 'pointer',
                background: currentView === 'items' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                color: currentView === 'items' ? '#ffffff' : '#a8a29e',
                borderLeft: currentView === 'items' ? '3px solid #ea580c' : '3px solid transparent',
                fontWeight: currentView === 'items' ? 600 : 500,
                fontSize: '0.875rem',
                transition: 'all 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (currentView !== 'items') {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.color = '#ffffff';
                }
              }}
              onMouseLeave={(e) => {
                if (currentView !== 'items') {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#a8a29e';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Layers size={17} />
                <span>Work Items</span>
              </div>
              {openCount > 0 && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.12rem 0.45rem',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                    color: '#f3f4f6',
                  }}
                >
                  {openCount}
                </span>
              )}
            </div>

            {/* Approvals */}
            <div
              onClick={() => setCurrentView('approvals')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.6rem 0.85rem',
                borderRadius: '6px',
                cursor: 'pointer',
                background: currentView === 'approvals' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                color: currentView === 'approvals' ? '#ffffff' : '#a8a29e',
                borderLeft: currentView === 'approvals' ? '3px solid #ea580c' : '3px solid transparent',
                fontWeight: currentView === 'approvals' ? 600 : 500,
                fontSize: '0.875rem',
                transition: 'all 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (currentView !== 'approvals') {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.color = '#ffffff';
                }
              }}
              onMouseLeave={(e) => {
                if (currentView !== 'approvals') {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = '#9ca3af';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <ShieldAlert size={17} />
                <span>Approvals</span>
              </div>
              {pendingApprovalsCount > 0 && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.12rem 0.45rem',
                    borderRadius: '9999px',
                    backgroundColor: '#854d0e',
                    color: '#fefce8',
                  }}
                >
                  {pendingApprovalsCount}
                </span>
              )}
            </div>
          </nav>
        </div>

        {/* Pinned User Profile Card at bottom of sidebar */}
        <div
          style={{
            paddingTop: '1rem',
            borderTop: '1px solid var(--sidebar-border)',
          }}
        >
          <div
            style={{
              padding: '0.75rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ position: 'relative' }}>
                <div
                  style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--color-primary)',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    fontFamily: 'var(--font-serif)',
                  }}
                >
                  {user?.name ? user.name.split(' ').map((n) => n[0]).join('') : 'U'}
                </div>
                <span
                  style={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: '9px',
                    height: '9px',
                    borderRadius: '50%',
                    backgroundColor: '#16a34a',
                    border: '2px solid var(--sidebar-bg)',
                  }}
                />
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: '#ffffff',
                    whiteSpace: 'nowrap',
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                  }}
                >
                  {user?.name}
                </div>
                <div
                  style={{
                    fontSize: '0.7rem',
                    color: '#a8a29e',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                  }}
                >
                  {activeTeam?.my_role ? (
                    <span style={{ textTransform: 'capitalize', color: '#fdba74' }}>
                      {activeTeam.my_role}
                    </span>
                  ) : (
                    'Member'
                  )}
                  <span>·</span>
                  <span>{activeTeam?.name || 'Workspace'}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => logout()}
              style={{
                background: 'none',
                border: 'none',
                color: '#9ca3af',
                cursor: 'pointer',
                padding: '0.35rem',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Sign out"
              onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#9ca3af')}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* 2. Top Header Bar (Clean warm white surface, natural gray borders) */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 40,
          height: '62px',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.5rem',
        }}
        className="keka-top-header"
      >
        {/* Left: Global Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', width: '360px', position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '0.85rem', color: '#6b7280' }} />
          <input
            type="text"
            placeholder="Search work items, records, documents..."
            onClick={() => setCurrentView('items')}
            className="input-field"
            style={{
              height: '36px',
              paddingLeft: '2.3rem',
              paddingRight: '4.5rem',
              fontSize: '0.825rem',
              background: '#f9fafb',
              borderColor: '#e5e7eb',
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: '0.65rem',
              fontSize: '0.7rem',
              fontWeight: 500,
              padding: '0.12rem 0.35rem',
              borderRadius: '4px',
              border: '1px solid #d1d5db',
              backgroundColor: '#ffffff',
              color: '#6b7280',
              pointerEvents: 'none',
            }}
          >
            Ctrl + K
          </div>
        </div>

        {/* Right Controls: Team Switcher, On-Duty pill, Notifications, Primary CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
          {/* Active Team Switcher */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowTeamMenu(!showTeamMenu)}
              className="btn btn-secondary"
              style={{
                height: '36px',
                padding: '0 0.85rem',
                fontSize: '0.825rem',
                borderColor: '#e5e7eb',
              }}
            >
              <Users size={14} color="var(--color-primary)" />
              <strong style={{ color: '#18181b', fontWeight: 600 }}>{activeTeam?.name || 'Select Team'}</strong>
              {activeTeam?.my_role && (
                <span className={`badge ${getRoleBadgeClass(activeTeam.my_role)}`} style={{ fontSize: '0.65rem' }}>
                  {activeTeam.my_role}
                </span>
              )}
              <ChevronDown size={13} color="#6b7280" />
            </button>

            {showTeamMenu && (
              <div
                className="keka-card"
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '115%',
                  width: '260px',
                  padding: '0.5rem',
                  zIndex: 100,
                  boxShadow: 'var(--shadow-lg)',
                }}
              >
                <div style={{ padding: '0.4rem 0.6rem', fontSize: '0.725rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase' }}>
                  ACTIVE TEAM
                </div>
                {teams.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => {
                      setActiveTeam(t);
                      setShowTeamMenu(false);
                    }}
                    style={{
                      padding: '0.5rem 0.75rem',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: activeTeam?.id === t.id ? 'var(--color-primary-subtle)' : 'transparent',
                    }}
                    onMouseEnter={(e) => {
                      if (activeTeam?.id !== t.id) e.currentTarget.style.backgroundColor = '#f9fafb';
                    }}
                    onMouseLeave={(e) => {
                      if (activeTeam?.id !== t.id) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#18181b' }}>{t.name}</div>
                      <div style={{ fontSize: '0.7rem', color: '#6b7280' }}>/{t.slug}</div>
                    </div>
                    {t.my_role && <span className={`badge ${getRoleBadgeClass(t.my_role)}`}>{t.my_role}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Duty Status Badge (Natural Forest Green) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.3rem 0.7rem',
              borderRadius: '9999px',
              backgroundColor: '#f0fdf4',
              border: '1px solid #bbf7d0',
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: '#16a34a',
              }}
            />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#166534' }}>
              On-Duty
            </span>
          </div>

          {/* Notifications Dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="btn btn-secondary"
              style={{
                height: '36px',
                width: '36px',
                padding: 0,
                position: 'relative',
              }}
              title="Notifications"
            >
              <Bell size={16} color="#4b5563" />
              {unreadCount > 0 && (
                <span
                  style={{
                    position: 'absolute',
                    top: '-3px',
                    right: '-3px',
                    background: 'var(--color-primary)',
                    color: '#ffffff',
                    fontSize: '0.65rem',
                    fontWeight: 600,
                    width: '17px',
                    height: '17px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div
                className="keka-card"
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '115%',
                  width: '340px',
                  maxHeight: '400px',
                  overflowY: 'auto',
                  padding: '0.875rem',
                  zIndex: 100,
                  boxShadow: 'var(--shadow-xl)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', paddingBottom: '0.5rem', borderBottom: '1px solid #f3f4f6' }}>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: '0.95rem', fontWeight: 600, color: '#18181b' }}>
                    System Notifications
                  </div>
                  <span style={{ fontSize: '0.725rem', color: '#6b7280' }}>
                    {unreadCount} unread
                  </span>
                </div>

                {!notifData?.notifications?.length ? (
                  <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#9ca3af', fontSize: '0.825rem' }}>
                    All notifications reviewed.
                  </div>
                ) : (
                  notifData.notifications.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: '0.625rem',
                        borderRadius: '6px',
                        background: n.read_at ? '#ffffff' : 'var(--color-primary-subtle)',
                        borderBottom: '1px solid #f3f4f6',
                        marginBottom: '0.35rem',
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        gap: '0.5rem',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#18181b' }}>
                          {n.kind.replace('.', ' ')}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                      {!n.read_at && (
                        <button
                          onClick={() => handleMarkRead(n.id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-primary)',
                            cursor: 'pointer',
                          }}
                          title="Mark read"
                        >
                          <CheckCircle2 size={15} />
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Primary CTA: + New Work Item */}
          <button
            onClick={() => {
              if (onOpenCreateItem) {
                onOpenCreateItem();
              } else {
                setCurrentView('items');
              }
            }}
            className="btn btn-primary"
            style={{
              height: '36px',
              padding: '0 0.95rem',
              fontWeight: 500,
            }}
          >
            <Plus size={15} />
            <span>New Work Item</span>
          </button>
        </div>
      </header>

      <style>{`
        @media (max-width: 991px) {
          .keka-sidebar {
            display: none !important;
          }
          .keka-top-header {
            margin-left: 0 !important;
          }
        }
        @media (min-width: 992px) {
          .keka-top-header {
            margin-left: 250px;
          }
        }
      `}</style>
    </>
  );
};

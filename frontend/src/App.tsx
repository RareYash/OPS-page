import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { useAuth } from './context/AuthContext';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { DashboardPage } from './pages/DashboardPage';
import { ItemDetailPage } from './pages/ItemDetailPage';
import { ItemsPage } from './pages/ItemsPage';
import { LoginPage } from './pages/LoginPage';

export type AppView = 'dashboard' | 'items' | 'approvals' | 'detail';

export const App: React.FC = () => {
  const { user, isLoading } = useAuth();
  const [currentView, setCurrentView] = useState<AppView>('dashboard');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  // Sync state with URL params on initial load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const viewParam = params.get('view');
    const itemParam = params.get('item');

    if (itemParam) {
      setSelectedItemId(itemParam);
      setCurrentView('detail');
    } else if (viewParam === 'items' || viewParam === 'dashboard' || viewParam === 'approvals') {
      setCurrentView(viewParam as AppView);
    }
  }, []);

  // Update URL params when view or selected item changes
  const navigateTo = (view: AppView, itemId?: string | null) => {
    const params = new URLSearchParams(window.location.search);
    if (view === 'detail' && itemId) {
      params.set('view', 'detail');
      params.set('item', itemId);
      setSelectedItemId(itemId);
    } else {
      params.delete('item');
      params.set('view', view);
      setSelectedItemId(null);
    }
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
    setCurrentView(view);
  };

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const itemParam = params.get('item');
      const viewParam = params.get('view');

      if (itemParam) {
        setSelectedItemId(itemParam);
        setCurrentView('detail');
      } else if (viewParam === 'items' || viewParam === 'approvals') {
        setSelectedItemId(null);
        setCurrentView(viewParam as AppView);
      } else {
        setSelectedItemId(null);
        setCurrentView('dashboard');
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-primary)',
          fontFamily: 'var(--font-serif)',
          fontSize: '1.15rem',
          fontWeight: 600,
          gap: '1rem',
          backgroundColor: 'var(--bg-workspace)',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            border: '3px solid #e5e7eb',
            borderTopColor: 'var(--color-primary)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }}
        />
        <div>Loading Operations Management Console...</div>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#fbfbfa' }}>
      <Navbar
        currentView={currentView}
        setCurrentView={(view) => navigateTo(view, null)}
        selectedItemId={selectedItemId}
      />

      <main className="keka-main-content" style={{ flex: 1, padding: '1.5rem' }}>
        {currentView === 'dashboard' && (
          <DashboardPage onSelectItem={(id) => navigateTo('detail', id)} />
        )}
        {currentView === 'items' && (
          <ItemsPage onSelectItem={(id) => navigateTo('detail', id)} />
        )}
        {currentView === 'approvals' && (
          <ApprovalsPage onSelectItem={(id) => navigateTo('detail', id)} />
        )}
        {currentView === 'detail' && selectedItemId && (
          <ItemDetailPage
            itemId={selectedItemId}
            onBack={() => navigateTo('items', null)}
          />
        )}
      </main>

      <style>{`
        @media (min-width: 992px) {
          .keka-main-content {
            margin-left: 250px;
          }
        }
      `}</style>
    </div>
  );
};

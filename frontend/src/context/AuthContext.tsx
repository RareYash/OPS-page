import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';
import { Team, User } from '../types';

interface AuthContextType {
  user: User | null;
  teams: Team[];
  activeTeam: Team | null;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  setActiveTeam: (team: Team) => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeam, setActiveTeam] = useState<Team | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSession = async () => {
    try {
      const currentUser = await api.auth.me();
      setUser(currentUser);
      const teamList = await api.teams.list();
      setTeams(teamList);
      if (teamList.length > 0 && !activeTeam) {
        setActiveTeam(teamList[0]);
      }
    } catch {
      setUser(null);
      setTeams([]);
      setActiveTeam(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSession();
  }, []);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    try {
      const u = await api.auth.login(email, pass);
      setUser(u);
      const teamList = await api.teams.list();
      setTeams(teamList);
      if (teamList.length > 0) {
        setActiveTeam(teamList[0]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignore network errors on logout
    }
    setUser(null);
    setTeams([]);
    setActiveTeam(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        teams,
        activeTeam,
        isLoading,
        login,
        logout,
        setActiveTeam,
        refreshUser: fetchSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar } from './components/Sidebar';
import { LoginPage } from './pages/LoginPage';
import { AdminDashboard } from './pages/AdminDashboard';
import { UserDashboard } from './pages/UserDashboard';
import { UserManagementPage } from './pages/UserManagementPage';
import { DocumentManagementPage } from './pages/DocumentManagementPage';
import { KnowledgeSearchPage } from './pages/KnowledgeSearchPage';
import { ExamsPage } from './pages/ExamsPage';
import { TakeExamPage } from './pages/TakeExamPage';
import { AIAssistantPage } from './pages/AIAssistantPage';
import { AnnouncementsPage } from './pages/AnnouncementsPage';
import { ProfilePage } from './pages/ProfilePage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { Loader2 } from 'lucide-react';

const ProtectedLayout: React.FC<{ children: React.ReactNode; allowedRoles?: ('ADMIN' | 'STUDENT')[] }> = ({
  children,
  allowedRoles
}) => {
  const { user, token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#090d16] flex items-center justify-center text-indigo-400">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'ADMIN' ? '/admin-dashboard' : '/user-dashboard'} replace />;
  }

  return (
    <div className="flex min-h-screen bg-dark-900">
      <Sidebar />
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Admin Routes */}
          <Route
            path="/admin-dashboard"
            element={
              <ProtectedLayout allowedRoles={['ADMIN']}>
                <AdminDashboard />
              </ProtectedLayout>
            }
          />
          <Route
            path="/user-management"
            element={
              <ProtectedLayout allowedRoles={['ADMIN']}>
                <UserManagementPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/knowledge-search"
            element={
              <ProtectedLayout allowedRoles={['ADMIN']}>
                <KnowledgeSearchPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <ProtectedLayout allowedRoles={['ADMIN']}>
                <AuditLogsPage />
              </ProtectedLayout>
            }
          />

          {/* Student Routes */}
          <Route
            path="/user-dashboard"
            element={
              <ProtectedLayout allowedRoles={['STUDENT']}>
                <UserDashboard />
              </ProtectedLayout>
            }
          />

          {/* Shared Protected Routes */}
          <Route path="/documents" element={<Navigate to="/study-plans" replace />} />
          <Route
            path="/exams"
            element={
              <ProtectedLayout>
                <ExamsPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/exams/:examId/take"
            element={
              <ProtectedLayout allowedRoles={['STUDENT']}>
                <TakeExamPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/ai-assistant"
            element={
              <ProtectedLayout>
                <AIAssistantPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/announcements"
            element={
              <ProtectedLayout>
                <AnnouncementsPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedLayout>
                <ProfilePage />
              </ProtectedLayout>
            }
          />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
};
export default App;

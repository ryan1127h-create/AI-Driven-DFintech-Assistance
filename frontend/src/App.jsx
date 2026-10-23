import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { RoleProvider, useRole } from "./context/RoleContext";
import { ChatProvider } from "./context/ChatContext";
import { canSeePage } from "./data/stages";
import Landing from "./pages/Landing";
import Register from "./pages/Register";
import Login from "./pages/Login";
import ProfilePage from "./pages/ProfilePage";
import ChecklistPage from "./pages/ChecklistPage";
import LifecyclePage from "./pages/LifecyclePage";
import AdminPage from "./pages/AdminPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AdminUserProfilePage from "./pages/AdminUserProfilePage";
import AdminApplicationsPage from "./pages/AdminApplicationsPage";
import AdminApplicationPage from "./pages/AdminApplicationPage";
import AdminProgramPage from "./pages/AdminProgramPage";
import AdminConversationPage from "./pages/AdminConversationPage";
import AdminConversationsPage from "./pages/AdminConversationsPage";
import AlumniMatchPage from "./pages/AlumniMatchPage";
import SupportRequestsPage from "./pages/SupportRequestsPage";
import AdminEscalationPage from "./pages/AdminEscalationPage";
import AdminAlumniPage from "./pages/AdminAlumniPage";
import AdminKnowledgePage from "./pages/AdminKnowledgePage";
import AdminKnowledgeCoursePage from "./pages/AdminKnowledgeCoursePage";
import AdminKnowledgeRecordPage from "./pages/AdminKnowledgeRecordPage";
import StudentLayout from "./components/student/StudentLayout";
import ChatWorkspace from "./components/student/ChatWorkspace";
import WorkspaceLayout from "./components/student/WorkspaceLayout";
import AdminLayout from "./components/admin/AdminLayout";

// Staff only use the staff console: the student app (chat, workspace,
// Alumni Match) sends them there.
function ProtectedRoute({ children, staffOnly, studentOnly, enrolledOnly }) {
  const { role, loading, isStaff } = useRole();
  if (loading) return null;
  if (!role) return <Navigate to="/login" replace />;
  if (staffOnly && !isStaff) return <Navigate to="/app" replace />;
  if (studentOnly && isStaff) return <Navigate to="/admin" replace />;
  if (enrolledOnly && role !== "enrolled_student") return <Navigate to="/app" replace />;
  return children;
}

// A workspace page only the lifecycle stages listed in data/stages.js see;
// anyone else typing its URL is sent back to the chat.
function StageRoute({ page, children }) {
  const { lifecycleStage } = useRole();
  if (!canSeePage(lifecycleStage, page)) return <Navigate to="/app" replace />;
  return children;
}

export default function App() {
  return (
    <ThemeProvider>
      <RoleProvider>
        <ChatProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              <Route element={<ProtectedRoute studentOnly><StudentLayout /></ProtectedRoute>}>
                <Route path="/app" element={<ChatWorkspace />} />
                <Route path="/alumni-match" element={<ProtectedRoute enrolledOnly><AlumniMatchPage /></ProtectedRoute>} />
                <Route path="/workspace" element={<WorkspaceLayout />}>
                  <Route path="profile" element={<ProfilePage />} />
                  <Route path="checklist" element={<StageRoute page="checklist"><ChecklistPage /></StageRoute>} />
                  <Route path="lifecycle" element={<StageRoute page="lifecycle"><LifecyclePage /></StageRoute>} />
                  <Route path="support" element={<SupportRequestsPage />} />
                </Route>
              </Route>

              <Route element={<ProtectedRoute staffOnly><AdminLayout /></ProtectedRoute>}>
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/users" element={<AdminUsersPage />} />
                <Route path="/admin/users/:userId" element={<AdminUserProfilePage />} />
                <Route path="/admin/applications" element={<AdminApplicationsPage />} />
                <Route path="/admin/applications/:applicationId" element={<AdminApplicationPage />} />
                <Route path="/admin/knowledge/programs/:programId" element={<AdminProgramPage />} />
                <Route path="/admin/conversations" element={<AdminConversationsPage />} />
                <Route path="/admin/conversations/:conversationId" element={<AdminConversationPage />} />
                <Route path="/admin/escalations" element={<AdminEscalationPage />} />
                <Route path="/admin/alumni" element={<AdminAlumniPage />} />
                <Route path="/admin/knowledge" element={<AdminKnowledgePage />} />
                <Route path="/admin/knowledge/courses/:courseCode" element={<AdminKnowledgeCoursePage />} />
                <Route path="/admin/knowledge/:category/:itemId" element={<AdminKnowledgeRecordPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ChatProvider>
      </RoleProvider>
    </ThemeProvider>
  );
}

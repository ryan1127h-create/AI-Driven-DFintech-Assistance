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
import StudentLayout from "./components/student/StudentLayout";
import ChatWorkspace from "./components/student/ChatWorkspace";
import WorkspaceLayout from "./components/student/WorkspaceLayout";

function ProtectedRoute({ children, staffOnly }) {
  const { role, loading, isStaff } = useRole();
  if (loading) return null;
  if (!role) return <Navigate to="/login" replace />;
  if (staffOnly && !isStaff) return <Navigate to="/app" replace />;
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

              <Route element={<ProtectedRoute><StudentLayout /></ProtectedRoute>}>
                <Route path="/app" element={<ChatWorkspace />} />
                <Route path="/workspace" element={<WorkspaceLayout />}>
                  <Route path="profile" element={<ProfilePage />} />
                  <Route path="checklist" element={<StageRoute page="checklist"><ChecklistPage /></StageRoute>} />
                  <Route path="lifecycle" element={<StageRoute page="lifecycle"><LifecyclePage /></StageRoute>} />
                </Route>
              </Route>

              <Route path="/admin" element={<ProtectedRoute staffOnly><AdminPage /></ProtectedRoute>} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ChatProvider>
      </RoleProvider>
    </ThemeProvider>
  );
}

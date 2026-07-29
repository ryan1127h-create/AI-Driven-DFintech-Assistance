import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { RoleProvider, useRole } from "./context/RoleContext";
import { ChatProvider } from "./context/ChatContext";
import Landing from "./pages/Landing";
import Register from "./pages/Register";
import StudentLayout from "./components/student/StudentLayout";
import ChatWorkspace from "./components/student/ChatWorkspace";
import WorkspaceLayout from "./components/student/WorkspaceLayout";
import AdminLayout from "./components/admin/AdminLayout";
import {
  DiscoverOverview, CurriculumPage, CareerOutcomesPage, ComparePage, FAQsPage, ScholarshipsPage,
} from "./components/student/discover";
import {
  ApplicationStatusPage, DocumentsPage, ChecklistPage, DeadlinesPage, GuidancePage,
  OfferAcceptancePage, RegistrationPage, HousingPage, OrientationPage, ImportantDatesPage,
} from "./components/student/application";
import {
  DegreePlannerPage, AcademicProgressPage, FinancialAidPage, LearningResourcesPage, CareerGuidancePage,
  GraduationAuditPage, RequirementTrackerPage, TranscriptPage, CareerPrepPage, AlumniPreviewPage,
  NetworkingPage, MentoringPage, EventsPage, CareerServicesPage, AlumniStoriesPage,
} from "./components/student/academic";
import {
  AdminDashboard, InquiriesPage, EscalationsPage, ApplicationsPage, StudentsPage,
  KnowledgeBasePage, AnalyticsPage, ActivityLogsPage, SettingsPage,
} from "./components/admin/pages";

function ProtectedRoute({ children, staffOnly }) {
  const { role } = useRole();
  if (!role) return <Navigate to="/" replace />;
  if (staffOnly && role !== "staff") return <Navigate to="/app" replace />;
  return children;
}

export default function App() {
  return (
    <ThemeProvider>
      <RoleProvider>
        <ChatProvider>
          <HashRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/register" element={<Register />} />

            {/* Student Portal */}
            <Route path="/app" element={<ProtectedRoute><StudentLayout /></ProtectedRoute>}>
              <Route index element={<ChatWorkspace />} />
            </Route>

            <Route path="/workspace" element={<ProtectedRoute><WorkspaceLayout /></ProtectedRoute>}>
              <Route path="discover" element={<DiscoverOverview />} />
              <Route path="curriculum" element={<CurriculumPage />} />
              <Route path="careers" element={<CareerOutcomesPage />} />
              <Route path="compare" element={<ComparePage />} />
              <Route path="faqs" element={<FAQsPage />} />
              <Route path="scholarships" element={<ScholarshipsPage />} />

              <Route path="application" element={<ApplicationStatusPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="checklist" element={<ChecklistPage />} />
              <Route path="deadlines" element={<DeadlinesPage />} />
              <Route path="guidance" element={<GuidancePage />} />

              <Route path="offer" element={<OfferAcceptancePage />} />
              <Route path="registration" element={<RegistrationPage />} />
              <Route path="housing" element={<HousingPage />} />
              <Route path="orientation" element={<OrientationPage />} />
              <Route path="dates" element={<ImportantDatesPage />} />

              <Route path="planner" element={<DegreePlannerPage />} />
              <Route path="progress" element={<AcademicProgressPage />} />
              <Route path="financial-aid" element={<FinancialAidPage />} />
              <Route path="resources" element={<LearningResourcesPage />} />
              <Route path="career-guidance" element={<CareerGuidancePage />} />

              <Route path="audit" element={<GraduationAuditPage />} />
              <Route path="tracker" element={<RequirementTrackerPage />} />
              <Route path="transcript" element={<TranscriptPage />} />
              <Route path="career-prep" element={<CareerPrepPage />} />
              <Route path="alumni-preview" element={<AlumniPreviewPage />} />

              <Route path="networking" element={<NetworkingPage />} />
              <Route path="mentoring" element={<MentoringPage />} />
              <Route path="events" element={<EventsPage />} />
              <Route path="career-services" element={<CareerServicesPage />} />
              <Route path="stories" element={<AlumniStoriesPage />} />
            </Route>

            {/* Staff/Admin Portal */}
            <Route path="/admin" element={<ProtectedRoute staffOnly><AdminLayout /></ProtectedRoute>}>
              <Route index element={<AdminDashboard />} />
              <Route path="inquiries" element={<InquiriesPage />} />
              <Route path="escalations" element={<EscalationsPage />} />
              <Route path="applications" element={<ApplicationsPage />} />
              <Route path="students" element={<StudentsPage />} />
              <Route path="knowledge" element={<KnowledgeBasePage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="logs" element={<ActivityLogsPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </HashRouter>
        </ChatProvider>
      </RoleProvider>
    </ThemeProvider>
  );
}

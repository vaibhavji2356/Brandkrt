import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/index.css";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import SiteLayout from "@/components/SiteLayout";
import ProtectedRoute from "@/components/ProtectedRoute";

import Landing from "@/pages/Landing";
import About from "@/pages/About";
import { Privacy, Terms, Refund } from "@/pages/legal/Legal";
import NotFound from "@/pages/NotFound";
import HelpCenter from "@/pages/HelpCenter";
import ErrorBoundary from "@/components/ErrorBoundary";

import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";
import ForgotPassword from "@/pages/auth/ForgotPassword";
import ResetPassword from "@/pages/auth/ResetPassword";
import VerifyEmail from "@/pages/auth/VerifyEmail";

import Profile from "@/pages/Profile";
import Settings from "@/pages/Settings";
import AdminLayout from "@/pages/admin/AdminLayout";
import AdminOverview from "@/pages/admin/AdminOverview";
import { AdminUsers, AdminVerification, AdminWithdrawals, AdminReports, AdminLogs } from "@/pages/admin/AdminSections";

import InfluencerLayout from "@/pages/influencer/InfluencerLayout";
import InfluencerOverview from "@/pages/influencer/InfluencerOverview";
import InfluencerProfile from "@/pages/influencer/InfluencerProfile";
import InfluencerCampaigns from "@/pages/influencer/InfluencerCampaigns";
import InfluencerEarnings from "@/pages/influencer/InfluencerEarnings";
import InfluencerNotifications from "@/pages/influencer/InfluencerNotifications";
import DashboardRedirect from "@/pages/influencer/DashboardRedirect";

import BrandLayout from "@/pages/brand/BrandLayout";
import BrandOverview from "@/pages/brand/BrandOverview";
import BrandProfile from "@/pages/brand/BrandProfile";
import BrandCampaigns from "@/pages/brand/BrandCampaigns";
import BrandCampaignDetails from "@/pages/brand/BrandCampaignDetails";
import BrandDiscover from "@/pages/brand/BrandDiscover";
import BrandSaved from "@/pages/brand/BrandSaved";
import BrandAnalytics from "@/pages/brand/BrandAnalytics";

import DealDetails from "@/pages/DealDetails";

// Part 4B — Collaborations · Messages · Agreements
import InfluencerCollaborations from "@/pages/influencer/InfluencerCollaborations";
import InfluencerAgreements from "@/pages/influencer/InfluencerAgreements";
import BrandAgreements from "@/pages/brand/BrandAgreements";
import Messages from "@/pages/Messages";
import AgreementDetails from "@/pages/AgreementDetails";

// Part 4C — Performance · Reports · Reviews
import InfluencerAnalytics from "@/pages/influencer/InfluencerAnalytics";
import BrandPerformance from "@/pages/brand/BrandPerformance";
import DealMetrics from "@/pages/DealMetrics";
import CampaignReport from "@/pages/CampaignReport";

function WithLayout({ children }) {
  return <SiteLayout>{children}</SiteLayout>;
}

export default function App() {
  return (
    <ErrorBoundary>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster richColors closeButton position="top-right" />
          <Routes>
            <Route path="/" element={<WithLayout><Landing /></WithLayout>} />
            <Route path="/about" element={<About />} />
            <Route path="/contact" element={<WithLayout><Landing /></WithLayout>} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/refund" element={<Refund />} />
            <Route path="/help" element={<HelpCenter />} />

            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />

            <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />

            <Route path="/admin" element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
              <Route index element={<AdminOverview />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="verification" element={<AdminVerification />} />
              <Route path="withdrawals" element={<AdminWithdrawals />} />
              <Route path="reports" element={<AdminReports />} />
              <Route path="logs" element={<AdminLogs />} />
            </Route>

            <Route path="/influencer" element={<ProtectedRoute><InfluencerLayout /></ProtectedRoute>}>
              <Route index element={<InfluencerOverview />} />
              <Route path="profile" element={<InfluencerProfile />} />
              <Route path="campaigns" element={<InfluencerCampaigns />} />
              <Route path="deals/:id" element={<DealDetails />} />
              <Route path="earnings" element={<InfluencerEarnings />} />
              <Route path="notifications" element={<InfluencerNotifications />} />
              <Route path="collaborations" element={<InfluencerCollaborations />} />
              <Route path="agreements" element={<InfluencerAgreements />} />
              <Route path="messages" element={<Messages />} />
              <Route path="analytics" element={<InfluencerAnalytics />} />
            </Route>

            <Route path="/brand" element={<ProtectedRoute><BrandLayout /></ProtectedRoute>}>
              <Route index element={<BrandOverview />} />
              <Route path="profile" element={<BrandProfile />} />
              <Route path="campaigns" element={<BrandCampaigns />} />
              <Route path="campaigns/:id" element={<BrandCampaignDetails />} />
              <Route path="deals/:id" element={<DealDetails />} />
              <Route path="discover" element={<BrandDiscover />} />
              <Route path="saved" element={<BrandSaved />} />
              <Route path="analytics" element={<BrandAnalytics />} />
              <Route path="agreements" element={<BrandAgreements />} />
              <Route path="messages" element={<Messages />} />
              <Route path="performance" element={<BrandPerformance />} />
            </Route>

            <Route path="/agreements/:id" element={<ProtectedRoute><AgreementDetails /></ProtectedRoute>} />
            <Route path="/deals/:id/metrics" element={<ProtectedRoute><DealMetrics /></ProtectedRoute>} />
            <Route path="/deals/:id/report" element={<ProtectedRoute><CampaignReport /></ProtectedRoute>} />

            <Route path="/dashboard" element={<DashboardRedirect />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
    </ErrorBoundary>
  );
}

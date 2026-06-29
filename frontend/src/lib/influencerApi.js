import api from "./api";

/* All influencer module API helpers in one tiny module so pages stay lean.
 * Each function returns the unwrapped payload (or empty list) so call-sites
 * don't have to know about the response envelope.
 */
export const InfluencerAPI = {
  getProfile: () => api.get("/influencers/me").then((r) => r.data.influencer),
  updateProfile: (payload) => api.put("/influencers/me", payload).then((r) => r.data.influencer),

  listDeals: (status) =>
    api
      .get("/deals", { params: status ? { status } : {} })
      .then((r) => r.data.deals || []),
  setDealStatus: (id, status) =>
    api.patch(`/deals/${id}/status`, { status }).then((r) => r.data),

  listPayments: () => api.get("/payments").then((r) => r.data.payments || []),

  submitVerification: (payload) =>
    api.post("/verification", payload).then((r) => r.data.request),
  myVerification: () =>
    api.get("/verification/mine").then((r) => r.data.requests || []),

  requestWithdrawal: (payload) =>
    api.post("/withdrawals", payload).then((r) => r.data.request),
  myWithdrawals: () =>
    api.get("/withdrawals/mine").then((r) => r.data.requests || []),

  listNotifications: () =>
    api.get("/notifications").then((r) => r.data.notifications || []),
  markNotificationRead: (id) =>
    api.post(`/notifications/${id}/read`).then((r) => r.data),

  getCampaign: (id) => api.get(`/campaigns/${id}`).then((r) => r.data.campaign),
};

export default InfluencerAPI;

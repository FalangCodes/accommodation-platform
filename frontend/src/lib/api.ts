import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://40.123.252.250:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach token to every request if available
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Auto refresh token on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refresh_token = localStorage.getItem("refresh_token");
        if (!refresh_token) throw new Error("No refresh token");
        const res = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
          refresh_token,
        });
        localStorage.setItem("access_token", res.data.access_token);
        localStorage.setItem("refresh_token", res.data.refresh_token);
        original.headers.Authorization = `Bearer ${res.data.access_token}`;
        return api(original);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ── AUTH ──────────────────────────────────────────────────────────────────────
export const authApi = {
  registerStudent: (data: { email: string; password: string }) =>
    api.post("/api/v1/auth/register/student", data),

  registerLandlord: (data: { email: string; password: string; display_name: string; contact_phone?: string }) =>
    api.post("/api/v1/auth/register/landlord", data),

  login: (data: { email: string; password: string }) =>
    api.post("/api/v1/auth/login", data),

  me: () => api.get("/api/v1/auth/me"),
};

// ── ACCOMMODATIONS ────────────────────────────────────────────────────────────
export const accommodationsApi = {
  search: (params: { university_id: number; radius_km?: number; price_min?: number; price_max?: number }) =>
    api.get("/api/v1/accommodations/search", { params }),

  list: () => api.get("/api/v1/accommodations"),

  get: (id: number) => api.get(`/api/v1/accommodations/${id}`),

  create: (data: any) => api.post("/api/v1/accommodations", data),

  analytics: (id: number) => api.get(`/api/v1/accommodations/${id}/analytics`),
};

// ── REVIEWS ───────────────────────────────────────────────────────────────────
export const reviewsApi = {
  getForAccommodation: (accommodation_id: number) =>
    api.get(`/api/v1/reviews/accommodation/${accommodation_id}`),

  submit: (data: { accommodation_id: number; rating: number; body: string }) =>
    api.post("/api/v1/reviews", data),

  delete: (review_id: number) => api.delete(`/api/v1/reviews/${review_id}`),

  reply: (review_id: number, body: string) =>
    api.post(`/api/v1/reviews/${review_id}/reply`, { body }),

  getMyReviews: () => api.get("/api/v1/reviews/my"),
};

// ── MODERATION ────────────────────────────────────────────────────────────────
export const moderationApi = {
  getPendingListings: () => api.get("/api/v1/moderation/listings/pending"),

  approveListing: (id: number) =>
    api.patch(`/api/v1/moderation/listings/${id}/approve`),

  rejectListing: (id: number, reason: string) =>
    api.patch(`/api/v1/moderation/listings/${id}/reject`, { reason }),

  removeReview: (id: number, reason: string) =>
    api.delete(`/api/v1/moderation/reviews/${id}`, { data: { reason } }),
};

// ── UNIVERSITIES ──────────────────────────────────────────────────────────────
export const universitiesApi = {
  list: () => api.get("/api/v1/universities"),
};
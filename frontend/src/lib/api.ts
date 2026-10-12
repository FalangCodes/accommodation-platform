import axios from "axios";
import { endSession } from "./session";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.kgotsofalangkakudi.co.za";

// Public authentication requests should not trigger session refresh or redirects.
const publicAuthApi = axios.create({ baseURL: API_BASE_URL });

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
let refreshInFlight: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const failure = error.response?.headers?.["x-auth-error"];
    if (failure === "account_inactive" || failure === "email_unverified" || failure === "session_revoked") {
      endSession(failure === "session_revoked" ? "session_expired" : failure);
      return Promise.reject(error);
    }
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");
      try {
        if (!refreshToken) throw new Error("No refresh token");
        if (!refreshInFlight) {
          refreshInFlight = axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          }).then((res) => {
            // A pending refresh must never restore a cleared or replaced session.
            if (localStorage.getItem("refresh_token") !== refreshToken) {
              throw new Error("Session changed during refresh");
            }
            localStorage.setItem("access_token", res.data.access_token);
            localStorage.setItem("refresh_token", res.data.refresh_token);
            return res.data.access_token as string;
          }).finally(() => { refreshInFlight = null; });
        }
        const accessToken = await refreshInFlight;
        if (localStorage.getItem("access_token") !== accessToken) {
          throw new Error("Session ended during refresh");
        }
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api(original);
      } catch (refreshError: unknown) {
        // A temporary throttle/storage outage must not erase a valid session.
        if (axios.isAxiosError(refreshError) &&
            (refreshError.response?.status === 429 || refreshError.response?.status === 503)) {
          return Promise.reject(refreshError);
        }
        if (localStorage.getItem("refresh_token") === refreshToken) {
          const refreshFailure = axios.isAxiosError(refreshError)
            ? refreshError.response?.headers?.["x-auth-error"] : undefined;
          endSession(refreshFailure === "account_inactive" || refreshFailure === "email_unverified"
            ? refreshFailure : "session_expired");
        }
      }
    }
    return Promise.reject(error);
  }
);

// ── AUTH ──────────────────────────────────────────────────────────────────────
export const authApi = {
  registerStudent: (data: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  student_number: string;
  }) => publicAuthApi.post("/api/v1/auth/register/student", data),

  registerLandlord: (data: {
    email: string;
    password: string;
    display_name: string;
    contact_phone?: string;
    bio?: string;
    website?: string;
    id_number: string;
    address_line1: string;
    address_line2?: string;
    city: string;
    province: string;
    postal_code: string;
  }) => publicAuthApi.post("/api/v1/auth/register/landlord", data),

  login: (data: { email: string; password: string }) =>
    publicAuthApi.post("/api/v1/auth/login", data),

  resendVerification: (email: string) => publicAuthApi.post("/api/v1/auth/resend-verification", { email }),
  verifyEmail: (token: string) => publicAuthApi.post("/api/v1/auth/verify-email", { token }),
  requestPasswordReset: (email: string) => publicAuthApi.post("/api/v1/auth/request-password-reset", { email }),
  resetPassword: (token: string, password: string) => publicAuthApi.post("/api/v1/auth/reset-password", { token, password }),

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

  myListings: () => api.get("/api/v1/accommodations/my"),

  uploadImage: (accommodationId: number, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post(`/api/v1/accommodations/${accommodationId}/images`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  },
  deleteImage: (accommodationId: number, imageId: number) =>
    api.delete(`/api/v1/accommodations/${accommodationId}/images/${imageId}`),
  recordView: (id: number) => api.post(`/api/v1/accommodations/${id}/view`),
  uploadOwnershipDoc: (accommodationId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/api/v1/accommodations/${accommodationId}/documents/ownership`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
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

  getModerationLog: (page: number = 1) =>
  api.get("/api/v1/moderation/log", { params: { page, page_size: 20 } }),
};

// ── UNIVERSITIES ──────────────────────────────────────────────────────────────
export const universitiesApi = {
  list: () => api.get("/api/v1/universities"),
};

// ── LANDLORDS ─────────────────────────────────────────────────────────────────
export const landlordsApi = {
  getMyProfile: () => api.get("/api/v1/landlords/me"),

  uploadIdCopy: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/api/v1/landlords/me/documents/id-copy", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  uploadProofOfAddress: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/api/v1/landlords/me/documents/proof-of-address", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  submitVerification: () => api.post("/api/v1/landlords/me/verification/submit"),

  getPendingVerifications: () => api.get("/api/v1/landlords/pending-verification"),

  verifyLandlord: (id: number) => api.patch(`/api/v1/landlords/${id}/verify`),

  rejectLandlord: (id: number, reason: string) =>
    api.patch(`/api/v1/landlords/${id}/reject-verification`, { reason }),
};

// ── ADMIN ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  getStats: () => api.get("/api/v1/admin/stats"),
  getUniversitiesTree: () => api.get("/api/v1/admin/universities/tree"),
  addUniversity: (data: { name: string; domain: string; province: string; lat: number; lng: number }) =>
    api.post("/api/v1/admin/universities", data),
  getStudents: () => api.get("/api/v1/admin/users/students"),
  getLandlords: () => api.get("/api/v1/admin/users/landlords"),
  getModerators: () => api.get("/api/v1/admin/users/moderators"),
  createModerator: (data: { email: string; password: string }) =>
    api.post("/api/v1/admin/moderators", data),
  deactivateUser: (id: number) => api.patch(`/api/v1/admin/users/${id}/deactivate`),
  activateUser: (id: number) => api.patch(`/api/v1/admin/users/${id}/activate`),
};

// ── REPORTS ───────────────────────────────────────────────────────────────────
export const reportsApi = {
  generate: (data: { report_type: string; year: number; month: number; entity_id?: number }) =>
    api.post("/api/v1/reports/generate", data),
  list: (params?: { report_type?: string; entity_id?: number }) =>
    api.get("/api/v1/reports", { params }),
  get: (id: number) => api.get(`/api/v1/reports/${id}`),
  getAccommodationTrend: (accommodationId: number) =>
    api.get(`/api/v1/reports/accommodation/${accommodationId}/trend`),
};

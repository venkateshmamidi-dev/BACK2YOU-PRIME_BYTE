/**
 * Back2You - API Service Client
 * Clean asynchronous interface for all backend endpoints.
 * Automatically adapts between unified FastAPI serving (port 8000)
 * and decoupled frontend static server (e.g. python -m http.server 5500).
 */

const API_BASE = window.BACK2YOU_API_URL
    || (window.__ENV__ && window.__ENV__.API_URL)
    || ((window.location.port === "8000" || window.location.port === "")
        ? "/api"
        : `${window.location.protocol}//${window.location.hostname}:8000/api`);

async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const token = localStorage.getItem("back2you_token");

    const headers = {
        "Accept": "application/json",
        ...(options.headers || {})
    };

    if (token && !headers["Authorization"]) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    // Default to JSON body if not FormData
    if (options.body && !(options.body instanceof FormData) && typeof options.body === "object") {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }

    try {
        const response = await fetch(url, { ...options, headers });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            const errorMsg = data.detail || data.message || "An unexpected error occurred. Please try again.";
            // If unauthorized on protected route, clear session and redirect if necessary
            if (response.status === 401 && !window.location.pathname.includes("login.html") && !window.location.pathname.includes("register.html")) {
                localStorage.removeItem("back2you_token");
                localStorage.removeItem("back2you_user");
            }
            throw new Error(errorMsg);
        }
        return data;
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        throw error;
    }
}

const API = {
    // Auth
    register: (userData) => apiFetch("/auth/register", { method: "POST", body: userData }),
    login: (credentials) => apiFetch("/auth/login", { method: "POST", body: credentials }),
    getCurrentUser: () => apiFetch("/auth/me"),

    // Items (Creation, Upload & Retrieval)
    reportLostItem: (itemData) => apiFetch("/items/lost", { method: "POST", body: itemData }),
    reportFoundItem: (itemData) => apiFetch("/items/found", { method: "POST", body: itemData }),

    // Universal createItem helper that handles both FormData and JSON objects
    createItem: async (itemInput) => {
        let type = "lost";
        let payload = {};

        if (itemInput instanceof FormData) {
            const rawType = (itemInput.get("type") || "lost").toString().toLowerCase();
            type = rawType === "found" ? "found" : "lost";

            let imageUrl = null;
            const imgFile = itemInput.get("image");
            if (imgFile instanceof File && imgFile.size > 0) {
                const uploadRes = await API.uploadImage(imgFile);
                imageUrl = uploadRes.image_url;
            }

            payload = {
                type: type,
                title: itemInput.get("title") || "",
                category: itemInput.get("category") || "",
                description: itemInput.get("description") || "",
                brand: itemInput.get("brand") || "",
                color: itemInput.get("color") || "",
                distinguishing_features: itemInput.get("distinguishing_features") || itemInput.get("reward_note") || itemInput.get("holding_location") || "",
                location: itemInput.get("location_description") || itemInput.get("location") || "",
                event_date: itemInput.get("date_occurred") || itemInput.get("event_date") || new Date().toISOString().split("T")[0],
                event_time: itemInput.get("time_occurred") || itemInput.get("event_time") || "12:00",
                image_url: imageUrl
            };
        } else {
            payload = { ...itemInput };
            type = (payload.type || "lost").toString().toLowerCase();
        }

        const endpoint = type === "found" ? "/items/found" : "/items/lost";
        const result = await apiFetch(endpoint, { method: "POST", body: payload });
        return result.item || result;
    },

    getLostItems: (params = {}) => {
        const q = new URLSearchParams(params).toString();
        return apiFetch(`/items/lost${q ? '?' + q : ''}`);
    },
    getFoundItems: (params = {}) => {
        const q = new URLSearchParams(params).toString();
        return apiFetch(`/items/found${q ? '?' + q : ''}`);
    },
    getMyItems: (itemType) => {
        const q = itemType ? `?item_type=${encodeURIComponent(itemType.toLowerCase())}` : "";
        return apiFetch(`/items/user/me${q}`);
    },
    getItemById: (id) => apiFetch(`/items/${id}`),
    getItem: (id) => apiFetch(`/items/${id}`),
    updateItem: (id, updates) => apiFetch(`/items/${id}`, { method: "PATCH", body: updates }),
    updateItemStatus: (id, status) => apiFetch(`/items/${id}`, { method: "PATCH", body: { status } }),
    deleteItem: (id) => apiFetch(`/items/${id}`, { method: "DELETE" }),
    uploadImage: (file) => {
        const formData = new FormData();
        formData.append("file", file);
        return apiFetch("/items/upload-image", { method: "POST", body: formData });
    },
    checkDuplicate: (itemData) => apiFetch("/items/check-duplicate", { method: "POST", body: itemData }),

    // Matching Engine
    findMatches: (itemId, limit = 5) => apiFetch(`/matching/find?item_id=${itemId}&limit=${limit}`, { method: "POST" }),
    getItemMatches: (itemId, limit = 5) => apiFetch(`/matching/${itemId}?limit=${limit}`),
    getMatches: (params = {}) => {
        const q = new URLSearchParams(params).toString();
        return apiFetch(`/matching${q ? '?' + q : ''}`);
    },
    getWeights: () => apiFetch("/matching/weights/current"),
    updateWeights: (weights) => apiFetch("/matching/weights/update", { method: "POST", body: weights }),

    // Claims & Verification
    submitClaim: (claimData) => apiFetch("/claims", { method: "POST", body: claimData }),
    getClaims: (status) => apiFetch(`/claims${status ? '?status=' + status : ''}`),
    getMyClaims: (status) => apiFetch(`/claims${status ? '?status=' + status : ''}`),
    getClaimById: (id) => apiFetch(`/claims/${id}`),
    updateClaim: (id, updateData) => apiFetch(`/claims/${id}`, { method: "PATCH", body: updateData }),

    // Community Helper & Gamification
    getGamification: () => apiFetch("/community/gamification"),
    getLeaderboard: (params = 15) => {
        const limit = typeof params === "object" ? (params.limit || 15) : params;
        return apiFetch(`/community/leaderboard?limit=${limit}`);
    },
    getBadges: () => apiFetch("/community/badges"),

    // Profile
    getProfile: async () => {
        const data = await apiFetch("/profile");
        // Flatten user & stats for seamless consumer consumption
        const user = data.user || {};
        const stats = data.stats || {};
        return {
            ...user,
            full_name: user.name,
            items_lost: stats.lost_reports || 0,
            items_found: stats.found_reports || 0,
            items_returned: stats.successful_recoveries || 0,
            helper_points: stats.points || 0,
            current_streak: stats.current_streak || 0,
            longest_streak: stats.longest_streak || 0,
            badge_level: stats.points >= 150 ? "CAMPUS GUARDIAN" : (stats.points >= 50 ? "ACTIVE HELPER" : "NEWCOMER"),
            badges: data.badges || [],
            recent_reports: data.recent_reports || []
        };
    },
    getProfileStats: () => apiFetch("/profile/stats"),
    updateProfile: (profileData) => apiFetch("/profile", { method: "PATCH", body: profileData }),
    changePassword: (passwordData) => apiFetch("/profile/change-password", { method: "POST", body: passwordData }),

    // Notifications
    getNotifications: (limit = 20) => apiFetch(`/notifications?limit=${limit}`),
    markNotificationRead: (id) => apiFetch(`/notifications/${id}/read`, { method: "PATCH" }),
    markAllNotificationsRead: () => apiFetch("/notifications/read-all", { method: "POST" }),

    // Admin & Moderation
    getAdminStats: () => apiFetch("/admin/statistics"),
    getAdminReports: (params = {}) => {
        const q = new URLSearchParams(params).toString();
        return apiFetch(`/admin/reports${q ? '?' + q : ''}`);
    },
    getAdminClaims: (status) => apiFetch(`/admin/claims${status ? '?status=' + status : ''}`),
    verifyClaim: (id, notes) => apiFetch(`/admin/claims/${id}/verify`, { method: "POST", body: { notes } }),
    rejectClaim: (id, reason) => apiFetch(`/admin/claims/${id}/reject`, { method: "POST", body: { reason } }),
    returnItem: (itemId) => apiFetch(`/admin/items/${itemId}/return`, { method: "POST" }),
    getEvaluation: () => apiFetch("/admin/evaluation"),
    seedBenchmarkData: () => apiFetch("/admin/seed-test-data", { method: "POST" })
};

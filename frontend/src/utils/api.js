// Utility to handle fetch requests with Auth header

export async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('token');

    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    const config = {
        ...options,
        headers,
    };

    const response = await fetch(url, config);

    // If 401 Unauthorized occurs, it means token is missing or expired
    if (response.status === 401) {
        // We can optionally clear local storage and force page reload
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('owner_id');
        window.location.reload();
    }

    return response;
}

// For endpoints that specifically need NO authentication header (like login/register)
export async function fetchWithoutAuth(url, options = {}) {
    return fetch(url, options);
}

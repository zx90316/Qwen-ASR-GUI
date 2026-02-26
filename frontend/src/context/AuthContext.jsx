import { createContext, useContext, useState, useEffect } from 'react';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [token, setToken] = useState(localStorage.getItem('token') || null);
    const [role, setRole] = useState(localStorage.getItem('role') || null);
    const [ownerId, setOwnerId] = useState(localStorage.getItem('owner_id') || null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        setIsLoading(false);
    }, []);

    const login = (userData) => {
        setToken(userData.access_token);
        setRole(userData.role);
        setOwnerId(userData.owner_id);
        localStorage.setItem('token', userData.access_token);
        localStorage.setItem('role', userData.role);
        localStorage.setItem('owner_id', userData.owner_id);
    };

    const logout = () => {
        setToken(null);
        setRole(null);
        setOwnerId(null);
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('owner_id');
    };

    return (
        <AuthContext.Provider value={{ token, role, ownerId, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);

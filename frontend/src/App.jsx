import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import TaskList from './pages/TaskList.jsx'
import NewTask from './pages/NewTask.jsx'
import TaskDetail from './pages/TaskDetail.jsx'
import SubSync from './pages/SubSync.jsx'
import LoginModal from './components/LoginModal.jsx'
import { useAuth } from './context/AuthContext.jsx'

function Layout({ children }) {
    const { token, role, ownerId, logout } = useAuth()

    return (
        <div className="app-layout">
            <aside className="sidebar">
                <div className="sidebar-brand">
                    <h1>🎙 Qwen ASR</h1>
                    <span>語音辨識平台</span>
                </div>
                {token && (
                    <div className="user-info" style={{ padding: '0 1.5rem', marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                        <div style={{ marginBottom: '4px' }}>身份: {role === 'guest' ? '訪客' : '一般用戶'}</div>
                        <div style={{ wordBreak: 'break-all' }}>ID: {ownerId}</div>
                        <button onClick={logout} className="btn btn-text btn-sm" style={{ marginTop: '8px', padding: '0', border: 'none', background: 'transparent', color: 'var(--color-primary)' }}>登出</button>
                    </div>
                )}
                <nav className="sidebar-nav">
                    <NavLink
                        to="/"
                        end
                        className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    >
                        <span className="icon">📋</span>
                        任務清單
                    </NavLink>
                    <NavLink
                        to="/new"
                        className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    >
                        <span className="icon">➕</span>
                        新增任務
                    </NavLink>
                    <NavLink
                        to="/subsync"
                        className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    >
                        <span className="icon">🎬</span>
                        SubSync
                    </NavLink>
                </nav>
            </aside>
            <main className="main-content">
                {children}
            </main>
        </div>
    )
}

export default function App() {
    const { token, isLoading } = useAuth()

    if (isLoading) return <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>載入中...</div>

    return (
        <BrowserRouter>
            {!token ? (
                <LoginModal />
            ) : (
                <Layout>
                    <Routes>
                        <Route path="/" element={<TaskList />} />
                        <Route path="/new" element={<NewTask />} />
                        <Route path="/tasks/:id" element={<TaskDetail />} />
                        <Route path="/subsync" element={<SubSync />} />
                    </Routes>
                </Layout>
            )}
        </BrowserRouter>
    )
}

import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import TaskList from './pages/TaskList.jsx'
import NewTask from './pages/NewTask.jsx'
import TaskDetail from './pages/TaskDetail.jsx'

function Layout({ children }) {
    return (
        <div className="app-layout">
            <aside className="sidebar">
                <div className="sidebar-brand">
                    <h1>🎙 Qwen ASR</h1>
                    <span>語音辨識平台</span>
                </div>
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
                </nav>
            </aside>
            <main className="main-content">
                {children}
            </main>
        </div>
    )
}

export default function App() {
    return (
        <BrowserRouter>
            <Layout>
                <Routes>
                    <Route path="/" element={<TaskList />} />
                    <Route path="/new" element={<NewTask />} />
                    <Route path="/tasks/:id" element={<TaskDetail />} />
                </Routes>
            </Layout>
        </BrowserRouter>
    )
}

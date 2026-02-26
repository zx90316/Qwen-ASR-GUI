import { fetchWithAuth } from '../utils/api';
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const STATUS_MAP = {
    pending: { label: '等待中', className: 'badge-pending' },
    processing: { label: '處理中', className: 'badge-processing' },
    completed: { label: '已完成', className: 'badge-completed' },
    failed: { label: '失敗', className: 'badge-failed' },
}

function formatDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-TW', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}

export default function TaskList() {
    const [tasks, setTasks] = useState([])
    const [filter, setFilter] = useState('all')
    const [loading, setLoading] = useState(true)
    const navigate = useNavigate()

    const fetchTasks = async () => {
        try {
            const params = filter !== 'all' ? `?status=${filter}` : ''
            const res = await fetchWithAuth(`/api/tasks${params}`)
            const data = await res.json()
            setTasks(data)
        } catch (err) {
            console.error('Failed to fetch tasks:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchTasks()
        const interval = setInterval(fetchTasks, 3000)
        return () => clearInterval(interval)
    }, [filter])

    const handleDelete = async (e, taskId) => {
        e.stopPropagation()
        if (!confirm('確定要刪除此任務？')) return
        try {
            await fetchWithAuth(`/api/tasks/${taskId}`, { method: 'DELETE' })
            setTasks(prev => prev.filter(t => t.id !== taskId))
        } catch (err) {
            console.error('Delete failed:', err)
        }
    }

    const filters = [
        { key: 'all', label: '全部' },
        { key: 'pending', label: '等待中' },
        { key: 'processing', label: '處理中' },
        { key: 'completed', label: '已完成' },
        { key: 'failed', label: '失敗' },
    ]

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>📋 任務清單</h2>
                <p>管理所有語音辨識任務</p>
            </div>

            <div className="filter-bar">
                {filters.map(f => (
                    <button
                        key={f.key}
                        className={`filter-chip ${filter === f.key ? 'active' : ''}`}
                        onClick={() => setFilter(f.key)}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="empty-state">
                    <div className="spinner" style={{ width: 32, height: 32 }}></div>
                    <p style={{ marginTop: 16 }}>載入中...</p>
                </div>
            ) : tasks.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <p>尚無任務紀錄</p>
                    <button className="btn btn-primary" onClick={() => navigate('/new')}>
                        ➕ 建立第一個任務
                    </button>
                </div>
            ) : (
                <div>
                    {tasks.map((task, i) => {
                        const status = STATUS_MAP[task.status] || STATUS_MAP.pending
                        return (
                            <div
                                key={task.id}
                                className="card card-clickable task-card fade-in"
                                style={{ animationDelay: `${i * 0.05}s` }}
                                onClick={() => navigate(`/tasks/${task.id}`)}
                            >
                                <div className="task-card-info">
                                    <div className="task-card-filename">
                                        {task.task_type === 'youtube' ? '📺 ' : (task.task_type === 'subsync_upload' ? '📁 ' : '🎵 ')}
                                        {task.filename || task.video_title}
                                    </div>
                                    <div className="task-card-meta">
                                        <span>{task.model}</span>
                                        <span>·</span>
                                        <span>{task.language}</span>
                                        <span>·</span>
                                        <span>{formatDate(task.created_at)}</span>
                                    </div>
                                    {task.status === 'processing' && (
                                        <div style={{ marginTop: 8 }}>
                                            <div className="progress-bar-container">
                                                <div
                                                    className="progress-bar-fill processing"
                                                    style={{ width: `${task.progress}%` }}
                                                />
                                            </div>
                                            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 4, display: 'block' }}>
                                                {task.progress_message} ({Math.round(task.progress)}%)
                                            </span>
                                        </div>
                                    )}
                                </div>
                                <div className="task-card-actions">
                                    <span className={`badge ${status.className}`}>
                                        {task.status === 'processing' && <span className="spinner" style={{ width: 10, height: 10 }} />}
                                        {status.label}
                                    </span>
                                    {task.status === 'completed' && (
                                        <button
                                            className="btn btn-outline btn-sm"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                navigate(`/subsync?taskId=${task.id}`);
                                            }}
                                            title="在 SubSync 開啟"
                                            style={{ marginRight: 8, borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}
                                        >
                                            🎬 SubSync
                                        </button>
                                    )}
                                    <button
                                        className="btn btn-outline btn-sm"
                                        onClick={(e) => handleDelete(e, task.id)}
                                        title="刪除"
                                    >
                                        🗑
                                    </button>
                                </div>
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

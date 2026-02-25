import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

const STATUS_MAP = {
    pending: { label: '等待中', className: 'badge-pending' },
    processing: { label: '處理中', className: 'badge-processing' },
    completed: { label: '已完成', className: 'badge-completed' },
    failed: { label: '失敗', className: 'badge-failed' },
}

function formatTime(seconds) {
    if (seconds == null) return '00:00'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 1000)
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

export default function TaskDetail() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [task, setTask] = useState(null)
    const [loading, setLoading] = useState(true)
    const [viewMode, setViewMode] = useState('merged')
    const [exportOpen, setExportOpen] = useState(false)
    const exportRef = useRef(null)

    const fetchTask = async () => {
        try {
            const res = await fetch(`/api/tasks/${id}`)
            if (!res.ok) throw new Error('任務不存在')
            const data = await res.json()
            setTask(data)
        } catch (err) {
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // 初始載入 + SSE 進度
    useEffect(() => {
        fetchTask()
    }, [id])

    // SSE 即時進度
    useEffect(() => {
        if (!task || (task.status !== 'pending' && task.status !== 'processing')) return

        const evtSource = new EventSource(`/api/tasks/${id}/progress`)

        evtSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data)
                setTask(prev => prev ? {
                    ...prev,
                    progress: data.percent,
                    progress_message: data.message,
                } : prev)

                if (data.done) {
                    evtSource.close()
                    // 重新載入完整任務資料
                    setTimeout(fetchTask, 500)
                }
            } catch { }
        }

        evtSource.onerror = () => {
            evtSource.close()
            // 嘗試重新拉資料
            setTimeout(fetchTask, 2000)
        }

        return () => evtSource.close()
    }, [task?.status, id])

    // 點擊外部關閉匯出選單
    useEffect(() => {
        const handleClick = (e) => {
            if (exportRef.current && !exportRef.current.contains(e.target)) {
                setExportOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClick)
        return () => document.removeEventListener('mousedown', handleClick)
    }, [])

    const handleExport = (format, variant) => {
        setExportOpen(false)
        window.open(`/api/tasks/${id}/export/${format}?variant=${variant}`, '_blank')
    }

    if (loading) {
        return (
            <div className="empty-state fade-in">
                <div className="spinner" style={{ width: 32, height: 32 }}></div>
                <p style={{ marginTop: 16 }}>載入中...</p>
            </div>
        )
    }

    if (!task) {
        return (
            <div className="empty-state fade-in">
                <div className="empty-icon">😵</div>
                <p>任務不存在或已被刪除</p>
                <button className="btn btn-primary" onClick={() => navigate('/')}>
                    返回清單
                </button>
            </div>
        )
    }

    const status = STATUS_MAP[task.status] || STATUS_MAP.pending
    const isCompleted = task.status === 'completed'
    const isProcessing = task.status === 'processing' || task.status === 'pending'

    return (
        <div className="fade-in">
            {/* 頁面標題 */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-xl)' }}>
                <div>
                    <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate('/')}
                        style={{ marginBottom: 'var(--space-sm)' }}
                    >
                        ← 返回清單
                    </button>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>🎵 {task.filename}</h2>
                    <div style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'center', marginTop: 'var(--space-sm)', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                        <span className={`badge ${status.className}`}>
                            {isProcessing && task.status === 'processing' && <span className="spinner" style={{ width: 10, height: 10 }} />}
                            {status.label}
                        </span>
                        <span>{task.model}</span>
                        <span>·</span>
                        <span>{task.language}</span>
                        {task.enable_diarization && <span>· 語者分離</span>}
                    </div>
                </div>

                {isCompleted && (
                    <div className="export-menu" ref={exportRef}>
                        <button
                            className="btn btn-accent"
                            onClick={() => setExportOpen(!exportOpen)}
                        >
                            📥 匯出結果
                        </button>
                        {exportOpen && (
                            <div className="export-dropdown">
                                <button className="export-dropdown-item" onClick={() => handleExport('txt', 'merged')}>
                                    📄 合併結果 TXT
                                </button>
                                <button className="export-dropdown-item" onClick={() => handleExport('txt', 'raw')}>
                                    📄 原始文字 TXT
                                </button>
                                <button className="export-dropdown-item" onClick={() => handleExport('txt', 'subtitle')}>
                                    📄 單句字幕 TXT
                                </button>
                                <button className="export-dropdown-item" onClick={() => handleExport('srt', 'merged')}>
                                    🎬 合併 SRT
                                </button>
                                <button className="export-dropdown-item" onClick={() => handleExport('srt', 'subtitle')}>
                                    🎬 單句字幕 SRT
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* 進度區塊（處理中） */}
            {isProcessing && (
                <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                        <span style={{ fontWeight: 600 }}>{task.progress_message}</span>
                        <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                            {Math.round(task.progress)}%
                        </span>
                    </div>
                    <div className="progress-bar-container" style={{ height: 10 }}>
                        <div
                            className="progress-bar-fill processing"
                            style={{ width: `${task.progress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* 錯誤訊息 */}
            {task.status === 'failed' && task.error_message && (
                <div className="card" style={{
                    marginBottom: 'var(--space-lg)',
                    borderColor: 'var(--color-error)',
                    background: 'var(--color-error-bg)',
                }}>
                    <p style={{ color: 'var(--color-error)', fontWeight: 600 }}>❌ 處理失敗</p>
                    <p style={{ color: 'var(--color-error)', fontSize: '0.9rem', marginTop: 'var(--space-sm)' }}>
                        {task.error_message}
                    </p>
                </div>
            )}

            {/* 結果區域 */}
            {isCompleted && (
                <div className="card">
                    <div className="result-tabs">
                        <button
                            className={`result-tab ${viewMode === 'merged' ? 'active' : ''}`}
                            onClick={() => setViewMode('merged')}
                        >
                            語者分離
                        </button>
                        <button
                            className={`result-tab ${viewMode === 'sentences' ? 'active' : ''}`}
                            onClick={() => setViewMode('sentences')}
                        >
                            單句結果
                        </button>
                        <button
                            className={`result-tab ${viewMode === 'raw' ? 'active' : ''}`}
                            onClick={() => setViewMode('raw')}
                        >
                            原始 ASR
                        </button>
                    </div>

                    {viewMode === 'merged' && task.merged_result && (
                        <div>
                            {task.merged_result.map((seg, i) => (
                                <div key={i} className="segment-block fade-in" style={{ animationDelay: `${i * 0.03}s` }}>
                                    <div className="segment-header">
                                        {seg.speaker && (
                                            <span className="speaker-badge">{seg.speaker}</span>
                                        )}
                                        <span className="segment-time">
                                            ⏱ {formatTime(seg.start)} → {formatTime(seg.end)}
                                        </span>
                                    </div>
                                    <div className="segment-text">{seg.text}</div>
                                </div>
                            ))}
                        </div>
                    )}

                    {viewMode === 'sentences' && task.sentences && (
                        <div>
                            {task.sentences.map((sent, i) => (
                                <div key={i} className="segment-block fade-in" style={{ animationDelay: `${i * 0.02}s` }}>
                                    <div className="segment-header">
                                        <span className="segment-time">
                                            ⏱ {formatTime(sent.start)} → {formatTime(sent.end)}
                                        </span>
                                    </div>
                                    <div className="segment-text">{sent.text}</div>
                                </div>
                            ))}
                        </div>
                    )}

                    {viewMode === 'raw' && (
                        <div style={{
                            background: 'var(--color-bg)',
                            borderRadius: 'var(--radius-md)',
                            padding: 'var(--space-lg)',
                            fontSize: '0.92rem',
                            lineHeight: 1.8,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                        }}>
                            {task.raw_text}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

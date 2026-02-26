import { fetchWithAuth } from '../utils/api';
import { useState, useEffect, useRef, useCallback } from 'react'
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
            const res = await fetchWithAuth(`/api/tasks/${id}`)
            if (!res.ok) throw new Error('任務不存在')
            const data = await res.json()
            setTask(data)
        } catch (err) {
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // ── LLM 潤飾/翻譯狀態 ──
    const [sentences, setSentences] = useState([])
    const [llmProviders, setLlmProviders] = useState({})
    const [llmProvider, setLlmProvider] = useState('')
    const [llmModel, setLlmModel] = useState('')
    const [llmAction, setLlmAction] = useState('polish') // polish | translate
    const [llmProgress, setLlmProgress] = useState(-1) // -1 尚未開始, 0-100 進度
    const [llmError, setLlmError] = useState('')
    const [llmCustomPrompt, setLlmCustomPrompt] = useState('')
    const [showCustomPrompt, setShowCustomPrompt] = useState(false)
    const [editingIndex, setEditingIndex] = useState(-1)
    const [editValue, setEditValue] = useState('')

    const [temperature, setTemperature] = useState(0.3)
    const [maxTokens, setMaxTokens] = useState(1024)
    const [thinkingLevel, setThinkingLevel] = useState('medium')

    const fetchLlmProviders = useCallback(async () => {
        try {
            const r = await fetchWithAuth('/api/llm/providers')
            if (r.ok) {
                const data = await r.json()
                setLlmProviders(data)
                const providers = Object.keys(data)
                if (providers.length > 0) {
                    setLlmProvider(providers[0])
                    setLlmModel(data[providers[0]][0] || '')
                }
            }
        } catch { }
    }, [])

    useEffect(() => {
        fetchLlmProviders()
    }, [fetchLlmProviders])

    // 初始化 sentences
    useEffect(() => {
        if (task && task.sentences && sentences.length === 0) {
            setSentences(task.sentences)
        }
    }, [task, sentences.length])

    // ── LLM 執行邏輯 ──
    const handleLlmProcess = async () => {
        if (!id || !llmProvider || !llmModel) return
        setLlmProgress(0)
        setLlmError('')
        setEditingIndex(-1)

        try {
            const resp = await fetchWithAuth('/api/llm/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: id,
                    task_type: 'asr',
                    provider: llmProvider,
                    model: llmModel,
                    action: llmAction,
                    custom_prompt: showCustomPrompt ? llmCustomPrompt : "",
                    temperature: parseFloat(temperature),
                    max_tokens: parseInt(maxTokens, 10),
                    thinking_level: thinkingLevel
                })
            })

            if (!resp.ok) throw new Error('啟動 LLM 處理失敗')

            const reader = resp.body.getReader()
            const decoder = new TextDecoder()

            let buffer = ""
            while (true) {
                const { value, done } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })

                const parts = buffer.split('\n\n')
                buffer = parts.pop() || ""

                for (const part of parts) {
                    if (part.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(part.substring(6))
                            setLlmProgress(data.percent)

                            if (data.done) {
                                if (data.sentences) {
                                    setSentences(data.sentences)
                                }
                                if (data.cancelled) {
                                    setLlmError('已中斷處理')
                                }
                                setTimeout(() => setLlmProgress(-1), 1000)
                            } else {
                                setSentences(prev => {
                                    const next = [...prev]
                                    const curr = next[data.index]
                                    next[data.index] = {
                                        ...curr,
                                        original_text: curr.original_text !== undefined ? curr.original_text : curr.text,
                                        text: data.processed_text
                                    }
                                    return next
                                })
                            }
                        } catch (e) { console.error('SSE JSON parse error', e) }
                    }
                }
            }
        } catch (e) {
            setLlmError(e.message)
            setLlmProgress(-1)
        }
    }

    // ── 中斷 LLM 處理 ──
    const handleLlmCancel = async () => {
        if (!id) return
        try {
            await fetchWithAuth('/api/llm/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: id, task_type: 'asr' })
            })
        } catch (e) { console.error('中斷失敗', e) }
    }

    // ── 保存最終字幕 ──
    const handleSaveSentences = async () => {
        if (!id) return
        try {
            const resp = await fetchWithAuth('/api/llm/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: id,
                    task_type: 'asr',
                    sentences: sentences
                })
            })
            if (resp.ok) {
                alert('字幕儲存成功！')
                fetchTask()
            }
        } catch { }
    }

    // ── 手動微調處理 ──
    const startEdit = (idx, currentText) => {
        setEditingIndex(idx)
        setEditValue(currentText)
    }

    const saveEdit = (idx) => {
        setSentences(prev => {
            const next = [...prev]
            if (next[idx].original_text === undefined && next[idx].text !== editValue) {
                next[idx].original_text = next[idx].text
            }
            next[idx].text = editValue
            return next
        })
        setEditingIndex(-1)
    }

    const handleRevertEdit = (e, idx) => {
        e.stopPropagation()
        setSentences(prev => {
            const next = [...prev]
            if (next[idx].original_text !== undefined) {
                next[idx].text = next[idx].original_text
                delete next[idx].original_text
            }
            return next
        })
    }

    const handleRevertAll = () => {
        if (!confirm('確定要復原所有字幕到最原始狀態嗎？此操作無法撤銷。')) return
        setSentences(prev => {
            return prev.map(s => {
                if (s.original_text !== undefined) {
                    const newS = { ...s, text: s.original_text }
                    delete newS.original_text
                    return newS
                }
                return s
            })
        })
    }

    // 初始載入 + SSE 進度
    useEffect(() => {
        fetchTask()
    }, [id])

    // SSE 即時進度
    useEffect(() => {
        if (!task || (task.status !== 'pending' && task.status !== 'processing')) return

        const token = localStorage.getItem('token') || '';
        const evtSource = new EventSource(`/api/tasks/${id}/progress?token=${token}`)

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
        const token = localStorage.getItem('token') || '';
        window.open(`/api/tasks/${id}/export/${format}?variant=${variant}&token=${token}`, '_blank')
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

                    {viewMode === 'sentences' && sentences && (
                        <div>
                            {/* ── LLM 工具列 ── */}
                            <div className="subsync-llm-toolbar" style={{ margin: '0 0 1rem 0', background: 'var(--color-surface)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }}>供應商</label>
                                        <select className="form-select" style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                                            value={llmProvider} onChange={e => {
                                                setLlmProvider(e.target.value)
                                                setLlmModel(llmProviders[e.target.value]?.[0] || '')
                                            }}>
                                            {Object.keys(llmProviders).map(p => <option key={p} value={p}>{p}</option>)}
                                        </select>
                                    </div>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }}>模型</label>
                                        <select className="form-select" style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                                            value={llmModel} onChange={e => setLlmModel(e.target.value)}>
                                            {(llmProviders[llmProvider] || []).map(m => <option key={m} value={m}>{m}</option>)}
                                        </select>
                                    </div>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }}>動作</label>
                                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                            <select className="form-select" style={{ padding: '4px 8px', fontSize: '0.8rem', width: 'auto' }}
                                                value={llmAction} onChange={e => setLlmAction(e.target.value)}>
                                                <option value="polish">✨ 語意潤飾</option>
                                                <option value="translate">🌐 翻譯繁中</option>
                                            </select>
                                            <button
                                                className={`btn btn-sm ${showCustomPrompt ? 'btn-accent' : 'btn-outline'}`}
                                                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                                onClick={() => setShowCustomPrompt(!showCustomPrompt)}
                                                title="自訂提示詞"
                                            >
                                                ✍️ 自訂
                                            </button>
                                        </div>
                                    </div>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }} title="數值越高越有創意 (0.0~2.0)">溫度</label>
                                        <input type="number" step="0.1" min="0" max="2" className="form-input" style={{ width: '60px', padding: '4px 8px', fontSize: '0.8rem' }}
                                            value={temperature} onChange={e => setTemperature(e.target.value)} />
                                    </div>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }} title="長度限制或思考長度">最大輸出</label>
                                        <input type="number" step="100" min="10" className="form-input" style={{ width: '70px', padding: '4px 8px', fontSize: '0.8rem' }}
                                            value={maxTokens} onChange={e => setMaxTokens(e.target.value)} />
                                    </div>
                                    <div className="subsync-llm-group">
                                        <label className="form-label" style={{ marginBottom: 2 }} title="支援思考等級之模型 (如 o1) 或傳給 Ollama 做參考">思考等級</label>
                                        <select className="form-select" style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                                            value={thinkingLevel} onChange={e => setThinkingLevel(e.target.value)}>
                                            <option value="low">低</option>
                                            <option value="medium">中</option>
                                            <option value="high">高</option>
                                        </select>
                                    </div>
                                    <div className="subsync-llm-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
                                        <button className="btn btn-accent btn-sm"
                                            disabled={llmProgress >= 0 || !llmModel}
                                            onClick={handleLlmProcess}>
                                            執行
                                        </button>
                                        {llmProgress >= 0 && (
                                            <button className="btn btn-danger btn-sm"
                                                onClick={handleLlmCancel}>
                                                ⏹ 中斷
                                            </button>
                                        )}
                                        {sentences.some(s => s.original_text !== undefined) && (
                                            <button className="btn btn-outline btn-sm"
                                                onClick={handleRevertAll}
                                                title="復原所有修改到原始字幕">
                                                ↩ 全部復原
                                            </button>
                                        )}
                                        <button className="btn btn-primary btn-sm"
                                            onClick={handleSaveSentences}
                                            disabled={llmProgress >= 0}>
                                            💾 儲存
                                        </button>
                                    </div>
                                </div>

                                {/* 自訂提示詞輸入區 */}
                                {showCustomPrompt && (
                                    <div style={{ width: '100%', marginTop: '12px' }}>
                                        <textarea
                                            className="form-input"
                                            placeholder={llmAction === 'polish' ?
                                                "請輸入自訂潤飾提示詞，例如：請幫我將這段字幕改成幽默的語氣，保留原意。" :
                                                "請輸入自訂翻譯提示詞，例如：將以下字幕翻譯成繁體中文，請使用台灣本土流行語。"
                                            }
                                            style={{ width: '100%', minHeight: '60px', fontSize: '0.85rem', resize: 'vertical' }}
                                            value={llmCustomPrompt}
                                            onChange={e => setLlmCustomPrompt(e.target.value)}
                                        />
                                    </div>
                                )}

                                {llmProgress >= 0 && (
                                    <div className="subsync-llm-progress-bar" style={{ marginTop: '12px', height: '4px', background: 'var(--color-border)', borderRadius: '2px', overflow: 'hidden' }}>
                                        <div className="subsync-llm-progress-fill" style={{ width: `${llmProgress}%`, height: '100%', background: 'var(--color-accent)', transition: 'width 0.3s' }}></div>
                                    </div>
                                )}
                                {llmError && <div style={{ color: 'var(--color-danger)', fontSize: '0.8rem', marginTop: '8px' }}>{llmError}</div>}
                            </div>

                            {/* 字幕列表 */}
                            <div className="subsync-subtitle-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {sentences.map((sent, i) => {
                                    const isModified = sent.original_text !== undefined && sent.original_text !== sent.text

                                    return (
                                        <div key={i} className="segment-block fade-in" style={{ animationDelay: `${i * 0.01}s`, cursor: 'pointer', padding: '12px', background: 'var(--color-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }} onDoubleClick={() => startEdit(i, sent.text)}>
                                            <div className="segment-header" style={{ marginBottom: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <span className="segment-time" style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                                    ⏱ {formatTime(sent.start)} → {formatTime(sent.end)}
                                                </span>
                                            </div>

                                            {editingIndex === i ? (
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                                    <textarea
                                                        className="form-input"
                                                        style={{ width: '100%', minHeight: '60px', padding: '8px', fontSize: '0.95rem', resize: 'vertical' }}
                                                        value={editValue}
                                                        onChange={e => setEditValue(e.target.value)}
                                                        onBlur={() => saveEdit(i)}
                                                        autoFocus
                                                        onClick={e => e.stopPropagation()}
                                                    />
                                                </div>
                                            ) : (
                                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                    {isModified && (
                                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                            <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', textDecoration: 'line-through' }}>
                                                                {sent.original_text}
                                                            </span>
                                                            <button
                                                                className="btn btn-sm btn-outline"
                                                                style={{ padding: '2px 6px', fontSize: '0.7rem', color: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}
                                                                onClick={(e) => handleRevertEdit(e, i)}
                                                                title="復原為原始字幕"
                                                            >
                                                                ↩ 復原
                                                            </button>
                                                        </div>
                                                    )}
                                                    <span style={{ fontSize: '1rem', marginTop: isModified ? '4px' : '0' }}>
                                                        {sent.text}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
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

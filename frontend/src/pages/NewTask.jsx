import { fetchWithAuth } from '../utils/api';
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export default function NewTask() {
    const [config, setConfig] = useState(null)
    const [file, setFile] = useState(null)
    const [model, setModel] = useState('')
    const [language, setLanguage] = useState('')
    const [diarization, setDiarization] = useState(true)
    const [traditional, setTraditional] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [dragOver, setDragOver] = useState(false)
    const fileInputRef = useRef(null)
    const navigate = useNavigate()

    useEffect(() => {
        fetchWithAuth('/api/config')
            .then(res => res.json())
            .then(data => {
                setConfig(data)
                const modelKeys = Object.keys(data.models)
                if (modelKeys.length > 0) setModel(modelKeys[0])
                const langKeys = Object.keys(data.languages)
                if (langKeys.length > 0) setLanguage(langKeys[0])
            })
            .catch(err => console.error('Failed to load config:', err))
    }, [])

    const handleDrop = (e) => {
        e.preventDefault()
        setDragOver(false)
        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile) setFile(droppedFile)
    }

    const handleSubmit = async () => {
        if (!file) return alert('請先選擇音訊檔案')
        setSubmitting(true)

        try {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('model', model)
            formData.append('language', language)
            formData.append('enable_diarization', diarization)
            formData.append('to_traditional', traditional)

            const token = localStorage.getItem('token') || '';
            const res = await fetchWithAuth(`/api/tasks?token=${token}`, {
                method: 'POST',
                body: formData,
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || '建立任務失敗')
            }

            const task = await res.json()
            navigate(`/tasks/${task.id}`)
        } catch (err) {
            alert(`錯誤: ${err.message}`)
            setSubmitting(false)
        }
    }

    if (!config) {
        return (
            <div className="empty-state fade-in">
                <div className="spinner" style={{ width: 32, height: 32 }}></div>
                <p style={{ marginTop: 16 }}>載入設定...</p>
            </div>
        )
    }

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>➕ 新增任務</h2>
                <p>上傳音訊檔案並設定辨識參數</p>
            </div>

            <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
                {/* 上傳區域 */}
                <div
                    className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDrop={handleDrop}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                    onDragLeave={() => setDragOver(false)}
                >
                    <input
                        type="file"
                        ref={fileInputRef}
                        style={{ display: 'none' }}
                        accept=".mp3,.wav,.m4a,.flac,.ogg,.wma,.aac,.mp4"
                        onChange={(e) => setFile(e.target.files[0])}
                    />
                    {file ? (
                        <>
                            <div className="upload-icon">🎵</div>
                            <p className="file-selected">{file.name}</p>
                            <p className="upload-hint">
                                {(file.size / 1024 / 1024).toFixed(1)} MB · 點擊重新選擇
                            </p>
                        </>
                    ) : (
                        <>
                            <div className="upload-icon">📁</div>
                            <p>點擊選擇或拖放音訊檔案</p>
                            <p className="upload-hint">
                                支援 MP3, WAV, M4A, FLAC, OGG, AAC, MP4
                            </p>
                        </>
                    )}
                </div>
            </div>

            {/* 設定面板 */}
            <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--space-lg)', color: 'var(--color-text)' }}>
                    ⚙ 辨識設定
                </h3>
                <div className="form-grid">
                    <div className="form-group">
                        <label className="form-label">模型</label>
                        <select
                            className="form-select"
                            value={model}
                            onChange={(e) => setModel(e.target.value)}
                        >
                            {Object.keys(config.models).map(key => (
                                <option key={key} value={key}>{key}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">語言</label>
                        <select
                            className="form-select"
                            value={language}
                            onChange={(e) => setLanguage(e.target.value)}
                        >
                            {Object.keys(config.languages).map(key => (
                                <option key={key} value={key}>{key}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group full-width">
                        <label className="form-label">選項</label>
                        <div className="checkbox-group">
                            <label className="checkbox-label">
                                <input
                                    type="checkbox"
                                    checked={diarization}
                                    onChange={(e) => setDiarization(e.target.checked)}
                                />
                                語者分離
                            </label>
                            <label className="checkbox-label">
                                <input
                                    type="checkbox"
                                    checked={traditional}
                                    onChange={(e) => setTraditional(e.target.checked)}
                                />
                                繁體中文
                            </label>
                        </div>
                    </div>
                </div>
            </div>

            {/* 提交按鈕 */}
            <div style={{ display: 'flex', gap: 'var(--space-md)', justifyContent: 'flex-end' }}>
                <button className="btn btn-outline" onClick={() => navigate('/')}>
                    取消
                </button>
                <button
                    className="btn btn-primary btn-lg"
                    onClick={handleSubmit}
                    disabled={!file || submitting}
                >
                    {submitting ? (
                        <>
                            <span className="spinner" />
                            提交中...
                        </>
                    ) : (
                        '🚀 開始辨識'
                    )}
                </button>
            </div>
        </div>
    )
}

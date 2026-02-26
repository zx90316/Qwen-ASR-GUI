import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { fetchWithoutAuth } from '../utils/api'; // We'll create this to avoid token looping during login
import './LoginModal.css';

export default function LoginModal() {
    const { login } = useAuth();
    const [step, setStep] = useState(1); // 1: Email, 2: Verification Code
    const [email, setEmail] = useState('');
    const [code, setCode] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSendCode = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await fetchWithoutAuth('/auth/send-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '發送失敗');
            }
            setStep(2);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleVerifyCode = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await fetchWithoutAuth('/auth/verify-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, code })
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '驗證失敗');
            }
            const data = await res.json();
            login(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleGuestLogin = async () => {
        setError('');
        setLoading(true);
        try {
            const res = await fetchWithoutAuth('/auth/guest', {
                method: 'POST'
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '訪客登入失敗');
            }
            const data = await res.json();
            login(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-modal-overlay">
            <div className="login-modal card">
                <h2>🔐 Qwen ASR 登入</h2>
                <p>請輸入您的 Email 來收取驗證碼</p>

                {error && <div className="login-error">{error}</div>}

                {step === 1 ? (
                    <form onSubmit={handleSendCode}>
                        <div className="form-group">
                            <label>Email 信箱</label>
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="name@example.com"
                                required
                            />
                        </div>
                        <div className="login-actions">
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? '發送中...' : '發送驗證碼'}
                            </button>
                            <button type="button" className="btn btn-outline" onClick={handleGuestLogin} disabled={loading}>
                                👻 以訪客身份繼續
                            </button>
                        </div>
                    </form>
                ) : (
                    <form onSubmit={handleVerifyCode}>
                        <div className="form-group">
                            <label>6 位數驗證碼</label>
                            <input
                                type="text"
                                value={code}
                                onChange={(e) => setCode(e.target.value)}
                                placeholder="123456"
                                maxLength={6}
                                required
                            />
                        </div>
                        <div className="login-actions">
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? '驗證中...' : '登入'}
                            </button>
                            <button type="button" className="btn btn-text" onClick={() => setStep(1)} disabled={loading}>
                                回上層重填 Email
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
}

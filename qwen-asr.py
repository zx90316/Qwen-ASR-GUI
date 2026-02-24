import torch
import numpy as np
import soundfile as sf
from qwen_asr import Qwen3ASRModel
from config import RESULT_DIR
from audio_utils import convert_to_wav, get_audio_duration
from opencc import OpenCC
from typing import List, Dict, Any
from pathlib import Path

# 繁簡轉換器
cc = OpenCC('s2twp')

# ============================================
# 音訊分段
# ============================================

def split_audio_by_silence(
    audio_path: str,
    target_duration: float = 120.0,
    max_duration: float = 180.0,
    silence_threshold_db: float = -40.0,
    min_silence_duration: float = 0.3,
    frame_duration: float = 0.02,
) -> List[tuple]:
    """
    依靜音段切分音訊，回傳各段 (start_sec, end_sec) 清單。

    Args:
        audio_path: WAV 檔案路徑
        target_duration: 目標片段長度（秒）
        max_duration: 最大片段長度（秒）
        silence_threshold_db: 靜音判定門檻（dB）
        min_silence_duration: 最小靜音持續時間（秒）
        frame_duration: RMS 計算窗口大小（秒）

    Returns:
        [(start, end), ...] 各段的起訖時間
    """
    total_duration = get_audio_duration(audio_path)

    # 短音訊不切分
    if total_duration <= target_duration:
        return [(0.0, total_duration)]

    print(f"🔍 偵測靜音段... (音訊長度: {total_duration:.1f}s)")

    # 讀取音訊計算 RMS 能量
    data, sr = sf.read(audio_path, dtype='float32')
    if data.ndim > 1:
        data = data.mean(axis=1)  # 混為單聲道

    frame_size = int(sr * frame_duration)
    num_frames = len(data) // frame_size
    threshold_linear = 10 ** (silence_threshold_db / 20.0)

    # 計算每個 frame 的 RMS
    rms_values = []
    for i in range(num_frames):
        frame = data[i * frame_size : (i + 1) * frame_size]
        rms = np.sqrt(np.mean(frame ** 2))
        rms_values.append(rms)

    # 偵測靜音區段
    silence_regions = []
    in_silence = False
    silence_start = 0

    for i, rms in enumerate(rms_values):
        time_sec = i * frame_duration
        if rms < threshold_linear:
            if not in_silence:
                in_silence = True
                silence_start = time_sec
        else:
            if in_silence:
                silence_end = time_sec
                duration = silence_end - silence_start
                if duration >= min_silence_duration:
                    silence_regions.append((silence_start, silence_end))
                in_silence = False

    # 結尾靜音
    if in_silence:
        silence_end = num_frames * frame_duration
        if silence_end - silence_start >= min_silence_duration:
            silence_regions.append((silence_start, silence_end))

    print(f"   找到 {len(silence_regions)} 個靜音區段")

    # 依靜音段選擇切分點
    chunks = []
    current_start = 0.0

    while current_start < total_duration:
        # 計算理想切分位置
        ideal_end = current_start + target_duration

        if ideal_end >= total_duration:
            # 剩餘部分不足，直接到尾端
            chunks.append((current_start, total_duration))
            break

        # 在 [ideal_end - 30s, ideal_end + 30s] 範圍內找最近的靜音段
        search_start = max(current_start + 60.0, ideal_end - 30.0)
        search_end = min(total_duration, current_start + max_duration)

        best_split = None
        best_distance = float("inf")

        for s_start, s_end in silence_regions:
            mid = (s_start + s_end) / 2
            if search_start <= mid <= search_end:
                dist = abs(mid - ideal_end)
                if dist < best_distance:
                    best_distance = dist
                    best_split = mid

        if best_split is not None:
            chunks.append((current_start, best_split))
            current_start = best_split
        else:
            # 找不到靜音段，強制切分
            forced_end = min(current_start + max_duration, total_duration)
            chunks.append((current_start, forced_end))
            current_start = forced_end

    print(f"📊 分段結果：{len(chunks)} 個片段")
    for i, (start, end) in enumerate(chunks):
        print(f"   片段 {i+1}: {start:.1f}s → {end:.1f}s ({end - start:.1f}s)")

    return chunks


# ============================================
# ASR 函式
# ============================================

def load_asr_model(max_new_tokens: int = 2048):
    """載入 ASR 模型（共用）"""
    model = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-1.7B",
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=32,
        max_new_tokens=max_new_tokens,
        forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
        forced_aligner_kwargs=dict(
            dtype=torch.bfloat16,
            device_map="cuda:0",
        ),
    )
    return model


def asr(audio_path, model=None):
    """執行單段 ASR 轉錄並回傳結果（含字元級時間戳）"""
    own_model = model is None
    if own_model:
        model = load_asr_model()

    results = model.transcribe(
        audio=[str(audio_path)],
        language=["Chinese"],
        return_time_stamps=True,
    )

    for r in results:
        print(f"  語言: {r.language}, 文字長度: {len(r.text)}")

    return results


def asr_chunked(audio_path, target_duration: float = 120.0):
    """
    分段處理長音訊的 ASR 轉錄。

    短音訊（≤ target_duration）直接整段轉錄；
    長音訊按靜音段切分後逐段轉錄，修正時間戳偏移再合併。

    Args:
        audio_path: WAV 音訊路徑
        target_duration: 切分目標長度（秒）

    Returns:
        所有段落的 ASR 結果列表（時間戳已偏移修正）
    """
    total_duration = get_audio_duration(str(audio_path))
    print(f"🎵 音訊長度: {total_duration:.1f}s")

    # 短音訊直接整段處理
    if total_duration <= target_duration:
        print("   短音訊，直接整段轉錄")
        model = load_asr_model()
        results = asr(audio_path, model=model)
        del model
        return results

    # 長音訊分段處理
    chunks = split_audio_by_silence(str(audio_path), target_duration=target_duration)

    model = load_asr_model()
    all_results = []

    result_dir = Path(audio_path).parent

    # 一次讀取完整音訊
    full_data, sr = sf.read(str(audio_path), dtype='float32')
    
    for i, (chunk_start, chunk_end) in enumerate(chunks):
        print(f"\n🔄 轉錄片段 {i+1}/{len(chunks)}: {chunk_start:.1f}s → {chunk_end:.1f}s")

        # 用 soundfile 直接切片寫出各段 WAV
        chunk_path = result_dir / f"chunk_{i}.wav"
        start_sample = int(chunk_start * sr)
        end_sample = int(chunk_end * sr)
        chunk_data = full_data[start_sample:end_sample]
        sf.write(str(chunk_path), chunk_data, sr)

        # ASR 轉錄
        chunk_results = asr(str(chunk_path), model=model)

        # 修正時間戳偏移（ForcedAlignItem 是 frozen dataclass，需用 replace）
        from dataclasses import replace as dc_replace
        for r in chunk_results:
            if hasattr(r, 'time_stamps') and r.time_stamps:
                new_timestamps = []
                for ts in r.time_stamps:
                    kwargs = {}
                    if hasattr(ts, 'start_time') and ts.start_time is not None:
                        kwargs['start_time'] = ts.start_time + chunk_start
                    if hasattr(ts, 'end_time') and ts.end_time is not None:
                        kwargs['end_time'] = ts.end_time + chunk_start
                    if kwargs:
                        new_timestamps.append(dc_replace(ts, **kwargs))
                    else:
                        new_timestamps.append(ts)
                r.time_stamps = new_timestamps

        all_results.extend(chunk_results)

        # 清理暫存檔
        try:
            chunk_path.unlink()
        except Exception:
            pass

    del model
    print(f"\n✅ 分段轉錄完成，共 {len(all_results)} 段結果")
    return all_results


# ============================================
# 繁體中文轉換
# ============================================

def convert_to_traditional(text: str) -> str:
    """將簡體中文轉換為繁體中文（台灣用語）"""
    return cc.convert(text)


# ============================================
# 語者分離
# ============================================

def diarization(audio_path):
    """執行語者分離並回傳 diarization 區段列表"""
    from pyannote.audio import Pipeline
    import torch
    from audio_utils import load_audio

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token="REMOVED_SECRET")

    pipeline.to(torch.device("cuda"))
    waveform, sample_rate = load_audio(str(audio_path))
    output = pipeline({"waveform": waveform, "sample_rate": sample_rate})

    # 取得語者分離 Annotation 物件
    diarization_result = output.speaker_diarization

    # 收集語者分離區段
    diar_segments = []
    for turn, _, speaker in diarization_result.itertracks(yield_label=True):
        diar_segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })
        print(f"{speaker} speaks between t={turn.start:.3f}s and t={turn.end:.3f}s")

    return diar_segments


# ============================================
# 合併 ASR + 語者分離
# ============================================

def merge_asr_with_diarization(
    asr_results,
    diar_segments: List[Dict],
    gap_threshold: float = 1.0,
    to_traditional: bool = True,
) -> List[Dict[str, Any]]:
    """
    將 ASR 字元級對齊結果與語者分離區段精準合併。

    核心邏輯：
    1. 取出 ASR 結果中每個 ForcedAlignItem 的字元與時間戳
    2. 以每個字元的時間中點匹配落入的語者分離區段
    3. 連續相同語者的字元合併為一個片段
    4. 相鄰同語者且時間間隔 < gap_threshold 的片段再次合併
    5. 可選：轉換為繁體中文

    Args:
        asr_results: ASR 轉錄結果列表（model.transcribe 回傳值）
        diar_segments: 語者分離區段列表 [{"start", "end", "speaker"}, ...]
        gap_threshold: 合併相鄰同語者片段的最大時間間隔（秒）
        to_traditional: 是否轉換為繁體中文

    Returns:
        合併結果 [{"start", "end", "speaker", "text"}, ...]
    """
    if not diar_segments:
        print("⚠️ 無語者分離資料，所有文字標記為 UNKNOWN")
        text = "".join(r.text for r in asr_results)
        if to_traditional:
            text = convert_to_traditional(text)
        return [{"start": 0.0, "end": 0.0, "speaker": "UNKNOWN", "text": text}]

    # --- Step 1: 取出所有字元的時間戳 ---
    chars = []
    for r in asr_results:
        if not hasattr(r, "time_stamps") or not r.time_stamps:
            continue
        for ts in r.time_stamps:
            char_text = getattr(ts, "text", "")
            start_time = getattr(ts, "start_time", None)
            end_time = getattr(ts, "end_time", None)
            if start_time is None or end_time is None:
                continue
            chars.append({
                "text": char_text,
                "start": float(start_time),
                "end": float(end_time),
            })

    if not chars:
        print("⚠️ ASR 結果中無字元級時間戳")
        text = "".join(r.text for r in asr_results)
        if to_traditional:
            text = convert_to_traditional(text)
        return [{"start": 0.0, "end": 0.0, "speaker": "UNKNOWN", "text": text}]

    print(f"📊 字元數: {len(chars)}，語者區段數: {len(diar_segments)}")

    # --- Step 2: 為每個字元匹配語者 ---
    import bisect
    diar_starts = [d["start"] for d in diar_segments]

    last_speaker = diar_segments[0]["speaker"]

    for char in chars:
        char_mid = (char["start"] + char["end"]) / 2
        speaker = None

        # 二分搜尋找到可能匹配的語者區段
        idx = bisect.bisect_right(diar_starts, char_mid) - 1
        if idx >= 0:
            for i in range(max(0, idx - 1), min(len(diar_segments), idx + 2)):
                d = diar_segments[i]
                if d["start"] <= char_mid <= d["end"]:
                    speaker = d["speaker"]
                    last_speaker = speaker
                    break

        # 若無精確匹配，找最接近的語者區段
        if speaker is None:
            min_dist = float("inf")
            for d in diar_segments:
                if char_mid < d["start"]:
                    dist = d["start"] - char_mid
                elif char_mid > d["end"]:
                    dist = char_mid - d["end"]
                else:
                    dist = 0
                if dist < min_dist:
                    min_dist = dist
                    speaker = d["speaker"]
            if min_dist > 2.0:
                speaker = last_speaker
            else:
                last_speaker = speaker

        char["speaker"] = speaker

    # --- Step 3: 按語者分組（語者變化時切段）---
    raw_segments = []
    current_speaker = chars[0]["speaker"]
    current_text = chars[0]["text"]
    current_start = chars[0]["start"]
    current_end = chars[0]["end"]

    for char in chars[1:]:
        if char["speaker"] == current_speaker:
            current_text += char["text"]
            current_end = char["end"]
        else:
            raw_segments.append({
                "start": current_start,
                "end": current_end,
                "speaker": current_speaker,
                "text": current_text,
            })
            current_speaker = char["speaker"]
            current_text = char["text"]
            current_start = char["start"]
            current_end = char["end"]

    # 最後一段
    raw_segments.append({
        "start": current_start,
        "end": current_end,
        "speaker": current_speaker,
        "text": current_text,
    })

    # --- Step 4: 合併相鄰同語者且時間接近的片段 ---
    merged = [raw_segments[0].copy()]
    for seg in raw_segments[1:]:
        prev = merged[-1]
        time_gap = seg["start"] - prev["end"]
        if seg["speaker"] == prev["speaker"] and time_gap < gap_threshold:
            prev["end"] = seg["end"]
            prev["text"] += seg["text"]
        else:
            merged.append(seg.copy())

    # --- Step 5: 過濾過短的雜訊片段（<0.05 秒且文字為空） ---
    final = []
    for seg in merged:
        duration = seg["end"] - seg["start"]
        text = seg["text"].strip()
        if duration < 0.05 and not text:
            continue
        final.append(seg)

    # --- Step 6: 繁體中文轉換 ---
    if to_traditional:
        for seg in final:
            seg["text"] = convert_to_traditional(seg["text"])

    print(f"✅ 合併完成：{len(chars)} 個字元 → {len(raw_segments)} 個原始片段 → {len(final)} 個最終片段")

    return final


# ============================================
# 工具函式
# ============================================

def format_time(seconds: float) -> str:
    """將秒數格式化為 HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"


# ============================================
# 主程式
# ============================================

if __name__ == "__main__":
    result_dir = RESULT_DIR / "test"
    result_dir.mkdir(parents=True, exist_ok=True)
    converted_path = result_dir / "converted.wav"
    convert_to_wav("audio.mp3", str(converted_path))

    # 執行分段 ASR
    asr_results = asr_chunked(converted_path)

    # 執行語者分離
    diar_segments = diarization(converted_path)

    # 合併結果（含繁體中文轉換）
    merged = merge_asr_with_diarization(asr_results, diar_segments)

    # 輸出結果
    print("\n" + "=" * 60)
    print("合併結果")
    print("=" * 60)
    for seg in merged:
        start_str = format_time(seg["start"])
        end_str = format_time(seg["end"])
        print(f"[{start_str} → {end_str}] {seg['speaker']}: {seg['text']}")


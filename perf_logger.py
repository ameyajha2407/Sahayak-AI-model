# perf_logger.py — Performance logger and log rotator for Sahayak AI.
# Logs every message interaction to logs/performance.csv with automatic weekly rotation.

import os
import csv
import time
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
PERF_LOG_PATH = os.path.join(LOGS_DIR, "performance.csv")

CSV_HEADER = [
    "date_time",
    "input_type",
    "language",
    "recording_length_s",
    "upload_time_s",
    "transcribe_time_s",
    "ttft_s",
    "total_reply_time_s",
    "model_name",
    "num_ai_calls",
    "prompt_size",
    "error",
]


def _rotate_logs_if_needed():
    """Rotate performance.csv weekly (older than 7 days) and clean up logs older than 7 days."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        if not os.path.exists(PERF_LOG_PATH):
            return

        mtime = os.path.getmtime(PERF_LOG_PATH)
        age_days = (time.time() - mtime) / 86400.0

        if age_days >= 7.0:
            # Rotate file
            dt_str = datetime.fromtimestamp(mtime).strftime("%Y_week_%U")
            rotated_path = os.path.join(LOGS_DIR, f"performance_{dt_str}.csv")
            if not os.path.exists(rotated_path):
                os.rename(PERF_LOG_PATH, rotated_path)

        # Cleanup rotated logs older than 14 days
        for fname in os.listdir(LOGS_DIR):
            fpath = os.path.join(LOGS_DIR, fname)
            if fname.startswith("performance_") and fname.endswith(".csv"):
                file_age_days = (time.time() - os.path.getmtime(fpath)) / 86400.0
                if file_age_days > 14.0:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[perf_logger] Rotation check error: {e}")


def init_perf_log():
    """Ensure logs directory and performance.csv exist with header."""
    try:
        _rotate_logs_if_needed()
        os.makedirs(LOGS_DIR, exist_ok=True)
        if not os.path.exists(PERF_LOG_PATH):
            with open(PERF_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER)
    except Exception as e:
        print(f"[perf_logger] Init error: {e}")


def log_performance(
    input_type: str = "typed",
    language: str = "en",
    recording_length_s: float = 0.0,
    upload_time_s: float = 0.0,
    transcribe_time_s: float = 0.0,
    ttft_s: float = 0.0,
    total_reply_time_s: float = 0.0,
    model_name: str = "demo",
    num_ai_calls: int = 1,
    prompt_size: int = 0,
    error: str = "",
    recording_duration_s: float = 0.0,
    transcription_time_s: float = 0.0,
    total_response_s: float = 0.0,
):
    """Append one interaction record to logs/performance.csv."""
    try:
        init_perf_log()
        rec_len = recording_length_s or recording_duration_s
        tr_time = transcribe_time_s or transcription_time_s
        tot_time = total_reply_time_s or total_response_s
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            input_type,
            language,
            f"{rec_len:.2f}",
            f"{upload_time_s:.2f}",
            f"{tr_time:.2f}",
            f"{ttft_s:.2f}",
            f"{tot_time:.2f}",
            model_name,
            num_ai_calls,
            prompt_size,
            error or "None",
        ]
        with open(PERF_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
    except Exception as e:
        print(f"[perf_logger] Failed to write log: {e}")


def get_recent_metrics(last_n: int = 10) -> dict:
    """Read the last N messages from performance.csv to calculate rolling averages for sidebar status."""
    try:
        if not os.path.exists(PERF_LOG_PATH):
            return {"reply_avg": None, "voice_avg": None, "recent_errors": 0, "model_status": "OK"}

        rows = []
        with open(PERF_LOG_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

        if not rows:
            return {"reply_avg": None, "voice_avg": None, "recent_errors": 0, "model_status": "OK"}

        recent = rows[-last_n:]
        reply_times = [float(r["total_reply_time_s"]) for r in recent if r.get("total_reply_time_s")]
        voice_times = [
            float(r["transcribe_time_s"]) + float(r["upload_time_s"])
            for r in recent
            if r.get("input_type") == "voice"
        ]
        errors = [r["error"] for r in recent if r.get("error") and r["error"] != "None"]

        reply_avg = (sum(reply_times) / len(reply_times)) if reply_times else None
        voice_avg = (sum(voice_times) / len(voice_times)) if voice_times else None

        status = "OK"
        if any("429" in e for e in errors):
            status = "Quota exhausted"
        elif any("503" in e for e in errors):
            status = "Server busy"
        elif any("timeout" in e.lower() for e in errors):
            status = "Timeout"

        return {
            "reply_avg": round(reply_avg, 2) if reply_avg is not None else None,
            "voice_avg": round(voice_avg, 2) if voice_avg is not None else None,
            "recent_errors": len(errors),
            "model_status": status,
        }
    except Exception as e:
        print(f"[perf_logger] Error reading metrics: {e}")
        return {"reply_avg": None, "voice_avg": None, "recent_errors": 0, "model_status": "OK"}

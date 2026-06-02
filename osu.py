#!/usr/bin/env python3
import json
import os
import sys
import threading
import time
import webbrowser
import traceback
from pathlib import Path
from tkinter import Tk, Label, Button, Entry, filedialog, StringVar, OptionMenu, Toplevel, messagebox
from typing import Any, Dict, List, Optional

import numpy as np
from osrparse import Replay, ReplayEvent
import pystray
from PIL import Image, ImageDraw, ImageFont
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# --- ИСПРАВЛЕНИЕ ПУТЕЙ ДЛЯ PYINSTALLER ---
if getattr(sys, 'frozen', False):
    # Если запущено как EXE — сохраняем файлы в папку РЯДОМ с EXE
    SCRIPT_DIR = Path(sys.executable).resolve().parent
else:
    # Если запущен обычный .py файл
    SCRIPT_DIR = Path(__file__).resolve().parent

CONFIG_FILE = SCRIPT_DIR / "config.json"
HISTORY_FILE = SCRIPT_DIR / "history.json"
DASHBOARD_FILE = SCRIPT_DIR / "osu_ai_dashboard.html"
# -----------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "replays_path": "",
    "experience_level": "Beginner",
    "accent_color": "#8b5cf6",
}

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)

def save_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def load_history() -> List[Dict[str, Any]]:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history: List[Dict[str, Any]]) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def first_run_setup() -> bool:
    root = Tk()
    root.title("osu! AI Coach - First Run Setup")
    root.geometry("480x300")
    root.resizable(False, False)

    label = Label(root, text="Welcome! Please configure osu! AI Coach.", font=("Segoe UI", 14))
    label.pack(pady=20)

    folder_var = StringVar()
    folder_entry = Entry(root, textvariable=folder_var, width=50)
    folder_entry.pack(pady=5)

    def browse_folder():
        folder = filedialog.askdirectory(title="Select your osu! Replays folder")
        if folder:
            folder_var.set(folder)

    browse_btn = Button(root, text="Browse Replays Folder", command=browse_folder)
    browse_btn.pack(pady=5)

    level_var = StringVar(value="Beginner")
    Label(root, text="Select your skill level:").pack(pady=(15,0))
    level_menu = OptionMenu(root, level_var, "Beginner", "Pro")
    level_menu.pack()

    def save_and_exit():
        replays_path = folder_var.get().strip()
        if not replays_path:
            messagebox.showwarning("Missing folder", "Please select your osu! Replays folder.")
            return
        if not os.path.isdir(replays_path):
            messagebox.showerror("Invalid folder", "The selected path does not exist.")
            return
        config = {
            "replays_path": replays_path,
            "experience_level": level_var.get(),
            "accent_color": DEFAULT_CONFIG["accent_color"],
        }
        save_config(config)
        root.destroy()

    cancel_btn = Button(root, text="Cancel", command=root.destroy)
    cancel_btn.pack(side="left", padx=20, pady=20)
    save_btn = Button(root, text="Save & Start", command=save_and_exit, bg="#8b5cf6", fg="white")
    save_btn.pack(side="right", padx=20, pady=20)

    root.mainloop()
    return CONFIG_FILE.exists()

def create_tray_icon(on_open_dashboard, on_scan_replays, on_reset_config, on_exit):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size-2, size-2], fill=(15, 23, 42, 255))
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    draw.text((size//2, size//2), "AI", fill=(139, 92, 246, 255), font=font, anchor="mm")
    draw.text((size//2-1, size//2-1), "AI", fill=(6, 182, 212, 200), font=font, anchor="mm")

    menu = (
        pystray.MenuItem("Open Dashboard", on_open_dashboard),
        pystray.MenuItem("Scan All Replays", on_scan_replays),
        pystray.MenuItem("Reset Configuration", on_reset_config),
        pystray.MenuItem("Exit", on_exit),
    )
    icon = pystray.Icon("osu_ai_coach", img, "osu! AI Coach", menu)
    return icon

class ReplayHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def _handle(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".osr"):
            time.sleep(0.3)
            t = threading.Thread(target=self.callback, args=(event.src_path,), daemon=True)
            t.start()

def process_replay(filepath: str) -> Optional[Dict[str, Any]]:
    try:
        replay = Replay.from_path(filepath)
    except Exception as e:
        print(f"Error reading replay {filepath}: {e}")
        traceback.print_exc()
        return None

    player = getattr(replay, 'username', None) or getattr(replay, 'player_name', None) or getattr(replay, 'player', 'Unknown')
    count300 = getattr(replay, 'count_300', 0)
    count100 = getattr(replay, 'count_100', 0)
    count50 = getattr(replay, 'count_50', 0)
    count_miss = getattr(replay, 'count_miss', 0)
    max_combo = getattr(replay, 'max_combo', 0)

    total_hits = count300 + count100 + count50 + count_miss
    if total_hits == 0:
        return None
    accuracy = (count300 + count100 * 0.3333 + count50 * 0.1666) / total_hits * 100.0

    replay_data = replay.replay_data
    if not replay_data:
        print("No replay data found.")
        return None

    keydown_events = []
    prev_keys = 0
    prev_time = 0

    for i, event in enumerate(replay_data):
        if hasattr(event, 'time_delta'):
            delta = event.time_delta
        elif hasattr(event, 'time_since_previous'):
            delta = event.time_since_previous
        elif hasattr(event, 'time'):
            if i == 0:
                prev_time = event.time
                current_keys = event.keys
                prev_keys = current_keys
                continue
            else:
                delta = event.time - prev_time
        else:
            delta = 0

        current_time = prev_time + delta
        prev_time = current_time
        current_keys = event.keys
        changed = current_keys & ~prev_keys
        if changed:
            if changed & (1 << 0):
                keydown_events.append((current_time, "K1"))
            if changed & (1 << 1):
                keydown_events.append((current_time, "K2"))
            if changed & (1 << 2):
                keydown_events.append((current_time, "M1"))
            if changed & (1 << 3):
                keydown_events.append((current_time, "M2"))
        prev_keys = current_keys

    if len(keydown_events) < 2:
        print(f"Only {len(keydown_events)} keydown events found – insufficient for UR.")
        return None

    times = [t for t, _ in keydown_events]
    intervals = np.diff(times)
    if len(intervals) == 0:
        return None
    std = np.std(intervals)
    ur = std * 10.0

    total_time = times[-1] - times[0] if len(times) > 1 else 1
    if total_time <= 0:
        total_time = 1
    third = total_time / 3.0
    start = times[0]
    sections = {"early": [], "mid": [], "late": []}
    for t in times:
        if t - start < third:
            sections["early"].append(t)
        elif t - start < 2 * third:
            sections["mid"].append(t)
        else:
            sections["late"].append(t)

    def section_ur(tlist):
        if len(tlist) < 2:
            return float('nan')
        diff = np.diff(tlist)
        return float(np.std(diff) * 10.0)

    ur_early = section_ur(sections["early"])
    ur_mid = section_ur(sections["mid"])
    ur_late = section_ur(sections["late"])

    config = load_config()
    experience = config.get("experience_level", "Beginner")
    verdict_lines = []

    if experience == "Beginner" or accuracy < 90.0:
        if ur > 180 and not np.isnan(ur):
            verdict_lines.append("High inconsistency detected. Try playing maps 10-20 BPM lower to build rhythm.")
        if accuracy > 95.0:
            verdict_lines.append("Mastery Achieved! You are outgrowing this difficulty. Move to +0.3* to +0.5* higher star maps.")
        if count_miss > 5:
            verdict_lines.append("Many misses – focus on reading simpler patterns. Slow down approach rate.")
        if not verdict_lines:
            verdict_lines.append("Good consistency for your level. Keep playing varied maps.")
    else:
        if accuracy > 95.0 and (not np.isnan(ur) and ur < 120):
            if not np.isnan(ur_late) and not np.isnan(ur_early) and (ur_late - ur_early > 15.0):
                verdict_lines.append("Muscle Fatigue / Stamina Depletion – Late-game UR increases significantly. Consider shorter sessions or warm-up.")
            if count_miss > 3:
                verdict_lines.append("Aim Overshoot or Snapping calibration issues – check your aim area and practice jumps.")
            if count100 > total_hits * 0.1:
                verdict_lines.append("High 100 count – possible slider break syndrome (releasing keys 10-30ms early). Focus on slider hold.")
            if not verdict_lines:
                verdict_lines.append("Excellent micro-optimization! Your consistency is top-tier.")
        else:
            verdict_lines.append("Your stats are improving. Keep refining rhythm and aim.")

    full_verdict = " ".join(verdict_lines) if verdict_lines else "No specific advice yet."

    result = {
        "filename": os.path.basename(filepath),
        "player": player,
        "count300": count300,
        "count100": count100,
        "count50": count50,
        "count_miss": count_miss,
        "max_combo": max_combo,
        "accuracy": round(accuracy, 2),
        "ur": round(ur, 2) if not np.isnan(ur) else 0.0,
        "ur_early": round(ur_early, 2) if not np.isnan(ur_early) else 0.0,
        "ur_mid": round(ur_mid, 2) if not np.isnan(ur_mid) else 0.0,
        "ur_late": round(ur_late, 2) if not np.isnan(ur_late) else 0.0,
        "verdict": full_verdict,
        "timestamp": time.time(),
        "full_combo": (count_miss == 0),
    }
    return result

def render_latest_cards(latest: Optional[Dict]) -> str:
    if not latest:
        return "<p class='text-slate-400'>No replay analyzed yet.</p>"
    return f"""
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">300</p>
            <p class="text-3xl font-bold neon-cyan">{latest['count300']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">100</p>
            <p class="text-3xl font-bold text-yellow-400">{latest['count100']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">50</p>
            <p class="text-3xl font-bold text-orange-400">{latest['count50']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Miss</p>
            <p class="text-3xl font-bold text-red-400">{latest['count_miss']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Accuracy</p>
            <p class="text-3xl font-bold text-green-400">{latest['accuracy']}%</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">UR</p>
            <p class="text-3xl font-bold text-cyan-400">{latest['ur']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Max Combo</p>
            <p class="text-3xl font-bold">{latest['max_combo']}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Player</p>
            <p class="text-lg font-bold truncate">{latest['player']}</p>
        </div>
    </div>
    """

def render_ai_verdict(latest: Optional[Dict]) -> str:
    if not latest:
        return ""
    return f"""
    <div class="bg-card rounded-xl p-4 mt-4 border-l-4" style="border-color: {load_config().get('accent_color','#8b5cf6')};">
        <h3 class="text-xl font-bold mb-2">🤖 AI Coach Live Verdict</h3>
        <p class="text-lg">{latest['verdict']}</p>
    </div>
    """

def render_mistakes(sorted_mistakes: List[tuple]) -> str:
    if not sorted_mistakes:
        return "<p class='text-slate-400'>No mistakes detected yet. Keep playing!</p>"
    lines = ""
    for mistake, count in sorted_mistakes:
        lines += f"<div class='bg-card rounded-xl p-3 mb-2 flex justify-between'><span>{mistake}</span><span class='text-cyan-400 font-bold'>{count}x</span></div>"
    return lines

def render_history_table(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "<p class='text-slate-400'>No replays analyzed yet.</p>"

    rows = ""
    for i, entry in enumerate(reversed(history)):
        num = len(history) - i
        fc_class = "text-green-400" if entry["full_combo"] else "text-red-400"
        fc_icon = "✅" if entry["full_combo"] else "❌"
        time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["timestamp"]))
        rows += f"""
        <tr class="border-b border-slate-700 hover:bg-slate-800/50 replay-row">
            <td class="py-2 px-3 text-center">{num}</td>
            <td class="py-2 px-3 truncate max-w-xs" title="{entry['filename']}">{entry['filename'][:40]}...</td>
            <td class="py-2 px-3 text-center">{entry['player']}</td>
            <td class="py-2 px-3 text-center text-green-400">{entry['accuracy']}%</td>
            <td class="py-2 px-3 text-center text-cyan-400">{entry['ur']}</td>
            <td class="py-2 px-3 text-center">{entry['max_combo']}x</td>
            <td class="py-2 px-3 text-center {fc_class}">{fc_icon}</td>
            <td class="py-2 px-3 text-xs text-slate-500">{time_str}</td>
        </tr>"""
    
    return f"""
    <div class="mb-4">
        <input id="historySearch" type="text" placeholder="🔍 Search by map name or player..."
               class="bg-slate-800 border border-slate-600 rounded-md p-2 w-full text-white"
               oninput="filterHistory()">
    </div>
    <div class="overflow-x-auto rounded-xl">
        <table class="w-full text-sm">
            <thead class="bg-slate-800 text-slate-400">
                <tr>
                    <th class="py-3 px-3 text-left">#</th>
                    <th class="py-3 px-3 text-left">Map</th>
                    <th class="py-3 px-3 text-left">Player</th>
                    <th class="py-3 px-3 text-center">Acc</th>
                    <th class="py-3 px-3 text-center">UR</th>
                    <th class="py-3 px-3 text-center">Combo</th>
                    <th class="py-3 px-3 text-center">FC</th>
                    <th class="py-3 px-3 text-center">Date</th>
                </tr>
            </thead>
            <tbody id="historyBody">
                {rows}
            </tbody>
        </table>
    </div>
    <script>
    function filterHistory() {{
        const input = document.getElementById('historySearch').value.toLowerCase();
        const rows = document.querySelectorAll('.replay-row');
        rows.forEach(row => {{
            const cells = row.querySelectorAll('td');
            const text = Array.from(cells).map(c => c.textContent.toLowerCase()).join(' ');
            row.style.display = text.includes(input) ? '' : 'none';
        }});
    }}
    </script>
    """

def render_aggregate_stats(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "<p class='text-slate-400'>No data yet.</p>"
    
    accuracies = [e["accuracy"] for e in history]
    urs = [e["ur"] for e in history]
    combos = [e["max_combo"] for e in history]
    misses = [e["count_miss"] for e in history]
    
    best_acc = max(accuracies)
    worst_acc = min(accuracies)
    avg_acc = round(np.mean(accuracies), 2)
    avg_ur = round(np.mean(urs), 2)
    best_ur = min(urs)
    worst_ur = max(urs)
    avg_combo = round(np.mean(combos))
    total_misses = sum(misses)
    fc_count = sum(1 for e in history if e["full_combo"])
    total_plays = len(history)
    
    fc_streak = 0
    current_streak = 0
    for e in reversed(history):
        if e["full_combo"]:
            current_streak += 1
            fc_streak = max(fc_streak, current_streak)
        else:
            current_streak = 0
    
    ur_trend = json.dumps(urs)
    ur_labels = json.dumps([f"#{i+1}" for i in range(len(history))])
    
    return f"""
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Total Plays</p>
            <p class="text-3xl font-bold text-white">{total_plays}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">FC Rate</p>
            <p class="text-3xl font-bold text-green-400">{fc_count}/{total_plays}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Best FC Streak</p>
            <p class="text-3xl font-bold text-cyan-400">{fc_streak}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Total Misses</p>
            <p class="text-3xl font-bold text-red-400">{total_misses}</p>
        </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Avg Accuracy</p>
            <p class="text-3xl font-bold text-green-400">{avg_acc}%</p>
            <p class="text-xs text-slate-500">Best: {best_acc}% / Worst: {worst_acc}%</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Avg UR</p>
            <p class="text-3xl font-bold text-cyan-400">{avg_ur}</p>
            <p class="text-xs text-slate-500">Best: {best_ur} / Worst: {worst_ur}</p>
        </div>
        <div class="bg-card rounded-xl p-4 text-center">
            <p class="text-slate-400">Avg Max Combo</p>
            <p class="text-3xl font-bold text-yellow-400">{avg_combo}x</p>
        </div>
    </div>
    <div class="bg-card rounded-xl p-4 mb-6">
        <h3 class="text-lg font-semibold mb-2 neon-cyan">UR Trend (All Sessions)</h3>
        <canvas id="urTrendChartAll" height="250"></canvas>
    </div>
    <script>
    new Chart(document.getElementById('urTrendChartAll'), {{
        type: 'line',
        data: {{
            labels: {ur_labels},
            datasets: [{{
                label: 'Overall UR',
                data: {ur_trend},
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139,92,246,0.2)',
                fill: true,
                tension: 0.3,
                pointRadius: 4
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                y: {{ beginAtZero: true, grid: {{ color: '#334155' }} }},
                x: {{ grid: {{ color: '#334155' }} }}
            }}
        }}
    }});
    </script>
    """

def generate_dashboard_html(history: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    if history:
        latest = history[-1]
    else:
        latest = None

    ur_trend = [entry["ur"] for entry in history]
    ur_labels = [f"#{i+1}" for i in range(len(history))]
    fc_chokes = [1 if entry["full_combo"] else 0 for entry in history]
    fc_count = sum(fc_chokes)
    choke_count = len(history) - fc_count

    mistakes = []
    for entry in history:
        v = entry.get("verdict", "")
        if "High inconsistency" in v:
            mistakes.append("Inconsistent rhythm")
        if "Muscle Fatigue" in v:
            mistakes.append("Stamina depletion (late-game)")
        if "Aim Overshoot" in v:
            mistakes.append("Aim overshoot/jump calibration")
        if "slider break" in v:
            mistakes.append("Slider-break syndrome")
        if "many misses" in v:
            mistakes.append("Reading / pattern recognition")
        if "Mastery Achieved" in v:
            mistakes.append("Outgrowing current difficulty (positive)")
    mistake_counts = {}
    for m in mistakes:
        mistake_counts[m] = mistake_counts.get(m, 0) + 1
    sorted_mistakes = sorted(mistake_counts.items(), key=lambda x: -x[1])

    accent = config.get("accent_color", "#8b5cf6")
    exp_level = config.get("experience_level", "Beginner")
    replays_path = config.get("replays_path", "")

    avg_ur = round(np.mean(ur_trend), 2) if ur_trend else 'N/A'

    early_ur = latest['ur_early'] if latest else 0
    mid_ur = latest['ur_mid'] if latest else 0
    late_ur = latest['ur_late'] if latest else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>osu! AI Coach Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
    body {{ background: #0f172a; color: #e2e8f0; }}
    .neon-violet {{ color: {accent}; }}
    .neon-cyan {{ color: #06b6d4; }}
    .bg-card {{ background: #1e293b; border: 1px solid #334155; }}
    .btn-neon {{ background: {accent}; color: white; }}
    .btn-neon:hover {{ filter: brightness(1.2); }}
    .tab-button.active {{ border-bottom: 2px solid {accent}; }}
</style>
</head>
<body class="min-h-screen p-6">
<div class="max-w-6xl mx-auto">
    <h1 class="text-4xl font-bold mb-6 neon-violet">🤖 osu! AI Coach</h1>
    <div class="flex border-b border-slate-700 mb-6">
        <button class="tab-button active px-6 py-3 text-lg font-semibold text-white" onclick="showTab('latest')">📊 Latest</button>
        <button class="tab-button px-6 py-3 text-lg font-semibold text-slate-400" onclick="showTab('stats')">📈 Stats</button>
        <button class="tab-button px-6 py-3 text-lg font-semibold text-slate-400" onclick="showTab('history')">📜 History</button>
        <button class="tab-button px-6 py-3 text-lg font-semibold text-slate-400" onclick="showTab('mistakes')">❌ Mistakes</button>
        <button class="tab-button px-6 py-3 text-lg font-semibold text-slate-400" onclick="showTab('account')">👤 Account</button>
    </div>

    <div id="tab-latest" class="tab-content">
        <h2 class="text-2xl font-bold mb-4 neon-cyan">Latest Replay Analysis</h2>
        {render_latest_cards(latest)}
        {render_ai_verdict(latest)}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div class="bg-card rounded-xl p-4">
                <h3 class="text-lg font-semibold mb-2 neon-cyan">Stamina Graph (UR per Stage)</h3>
                <canvas id="staminaChart" height="200"></canvas>
            </div>
            <div class="bg-card rounded-xl p-4">
                <h3 class="text-lg font-semibold mb-2 neon-cyan">Hit Error Distribution</h3>
                <canvas id="hitErrorChart" height="200"></canvas>
            </div>
        </div>
    </div>

    <div id="tab-stats" class="tab-content hidden">
        <h2 class="text-2xl font-bold mb-4 neon-cyan">📈 Current Aggregate Stats</h2>
        {render_aggregate_stats(history)}
    </div>

    <div id="tab-history" class="tab-content hidden">
        <h2 class="text-2xl font-bold mb-4 neon-cyan">📜 Full Replay History</h2>
        {render_history_table(history)}
    </div>

    <div id="tab-mistakes" class="tab-content hidden">
        <h2 class="text-2xl font-bold mb-4 neon-cyan">Diagnosis Board</h2>
        {render_mistakes(sorted_mistakes)}
    </div>

    <div id="tab-account" class="tab-content hidden">
        <h2 class="text-2xl font-bold mb-4 neon-cyan">Settings</h2>
        <div class="bg-card rounded-xl p-6 space-y-4">
            <div>
                <label class="block text-sm font-medium mb-1">Experience Level</label>
                <select id="expLevel" class="bg-slate-800 border border-slate-600 rounded-md p-2 w-48">
                    <option value="Beginner" {"selected" if exp_level=='Beginner' else ""}>Beginner</option>
                    <option value="Pro" {"selected" if exp_level=='Pro' else ""}>Pro</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium mb-1">Accent Theme Color</label>
                <input type="color" id="accentColor" value="{accent}" class="h-10 w-20 rounded">
            </div>
            <div>
                <label class="block text-sm font-medium mb-1">Replays Folder</label>
                <input type="text" id="replaysPath" value="{replays_path}" class="bg-slate-800 border border-slate-600 rounded-md p-2 w-full">
            </div>
            <button onclick="saveSettings()" class="btn-neon px-6 py-2 rounded-md font-semibold">💾 Save Settings</button>
            <p id="saveMsg" class="text-green-400 hidden">Settings saved!</p>
        </div>
    </div>
</div>

<script>
function showTab(tabId) {{
    document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
    document.getElementById('tab-' + tabId).classList.remove('hidden');
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active', 'text-white'));
    document.querySelectorAll('.tab-button').forEach(b => b.classList.add('text-slate-400'));
    const buttons = document.querySelectorAll('.tab-button');
    const idx = ['latest','stats','history','mistakes','account'].indexOf(tabId);
    if (idx >=0) {{
        buttons[idx].classList.add('active');
        buttons[idx].classList.remove('text-slate-400');
        buttons[idx].classList.add('text-white');
    }}
}}

function saveSettings() {{
    const level = document.getElementById('expLevel').value;
    const color = document.getElementById('accentColor').value;
    const path = document.getElementById('replaysPath').value;
    document.getElementById('saveMsg').classList.remove('hidden');
    document.getElementById('saveMsg').innerText = 'Please update config.json manually or restart the coach for changes to take effect. Values: level='+level+', color='+color+', path='+path;
}}

new Chart(document.getElementById('staminaChart'), {{
    type: 'line',
    data: {{
        labels: ['Early-Game', 'Mid-Game', 'Late-Game'],
        datasets: [{{
            label: 'UR',
            data: [{early_ur}, {mid_ur}, {late_ur}],
            borderColor: '#06b6d4',
            backgroundColor: 'rgba(6,182,212,0.2)',
            fill: true,
            tension: 0.3
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            y: {{ beginAtZero: true, grid: {{ color: '#334155' }} }},
            x: {{ grid: {{ color: '#334155' }} }}
        }}
    }}
}});
new Chart(document.getElementById('hitErrorChart'), {{
    type: 'bar',
    data: {{
        labels: ['Early', 'Mid', 'Late'],
        datasets: [{{
            label: 'UR (Hit Error Proxy)',
            data: [{early_ur}, {mid_ur}, {late_ur}],
            backgroundColor: ['#8b5cf6', '#06b6d4', '#f59e0b']
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            y: {{ beginAtZero: true, grid: {{ color: '#334155' }} }},
            x: {{ grid: {{ color: '#334155' }} }}
        }}
    }}
}});
new Chart(document.getElementById('urTrendChart'), {{
    type: 'line',
    data: {{
        labels: {json.dumps(ur_labels)},
        datasets: [{{
            label: 'Overall UR',
            data: {json.dumps(ur_trend)},
            borderColor: '#8b5cf6',
            backgroundColor: 'rgba(139,92,246,0.2)',
            fill: true,
            tension: 0.3,
            pointRadius: 4
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            y: {{ beginAtZero: true, grid: {{ color: '#334155' }} }},
            x: {{ grid: {{ color: '#334155' }} }}
        }}
    }}
}});
</script>
</body>
</html>"""
    return html

def on_replay_created(filepath: str):
    print(f"New replay detected: {filepath}")
    result = process_replay(filepath)
    if result is None:
        print("Failed to process replay.")
        return
    history = load_history()
    history.append(result)
    if len(history) > 10:
        history = history[-10:]
    save_history(history)
    config = load_config()
    html = generate_dashboard_html(history, config)
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open(DASHBOARD_FILE.resolve().as_uri())
    print("Dashboard updated and opened.")

def process_existing_replays(replays_dir: str):
    files = sorted(Path(replays_dir).glob("*.osr"), key=lambda p: p.stat().st_ctime)
    for filepath in files:
        print(f"Processing existing replay: {filepath.name}")
        on_replay_created(str(filepath))

def on_open_dashboard(icon, item):
    history = load_history()
    config = load_config()
    html = generate_dashboard_html(history, config)
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open(DASHBOARD_FILE.resolve().as_uri())

def on_scan_replays(icon, item):
    config = load_config()
    replays_dir = config.get("replays_path", "")
    if replays_dir and Path(replays_dir).is_dir():
        process_existing_replays(replays_dir)
    else:
        print("No valid replays path configured.")

def on_reset_config(icon, item):
    if CONFIG_FILE.exists():
        os.remove(CONFIG_FILE)
        print("Configuration reset. Restart required.")
        icon.stop()
        sys.exit(0)
    else:
        print("No config to reset.")

def on_exit(icon, item):
    icon.stop()
    sys.exit(0)

def main():
    config = load_config()
    if not config.get("replays_path") or not Path(config["replays_path"]).is_dir():
        if not first_run_setup():
            print("Configuration cancelled. Exiting.")
            sys.exit(0)
        config = load_config()

    replays_dir = config["replays_path"]
    if not Path(replays_dir).is_dir():
        print(f"Replays directory {replays_dir} not found. Please check config.json")
        sys.exit(1)

    event_handler = ReplayHandler(on_replay_created)
    observer = Observer()
    observer.schedule(event_handler, replays_dir, recursive=False)
    observer.start()
    print(f"Monitoring {replays_dir} for new .osr files...")

    existing_thread = threading.Thread(target=process_existing_replays, args=(replays_dir,), daemon=True)
    existing_thread.start()

    icon = create_tray_icon(on_open_dashboard, on_scan_replays, on_reset_config, on_exit)
    icon.run()

if __name__ == "__main__":
    main()

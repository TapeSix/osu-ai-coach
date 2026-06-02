# osu! AI Coach 🎯🤖

An automated tool that analyzes your osu! replays in real-time and generates detailed performance insights directly in your web browser.

> **Disclaimer / Honestly speaking:** Look, I'm too lazy to code everything from scratch, so like 90% of this was generated with AI (LLMs). It actually works though. If the code looks weird, that's why. But hey, as long as it spits out accurate stats and helps us hit those circles better, who cares? ¯\_(ツ)_/¯

## ✨ Features
- **Real-time Monitoring**: Automatically detects and processes new `.osr` files as soon as you finish a map. No manual uploading needed.
- **Advanced Unstable Rate (UR) Analysis**: Calculates overall click stability and breaks it down into sections (Early, Mid, and Late game) to see exactly where your stamina or focus drops.
- **Interactive Dashboard**: Generates a clean, local HTML report featuring charts, stats, and personalized coaching advice to improve your gameplay.
- **Background Mode**: Seamlessly minimizes into the system tray so it doesn't interfere with your gaming sessions or drop your FPS.

## 🚀 How to Run (For Players)
1. 📥 **[Download the latest osu.exe here](https://github.com)**
2. Run the executable and select your osu! Replays folder (typically `Data/r` inside your osu! directory).
3. Just play any map — your personal dashboard will update automatically in the background!


## 🛠️ Development & Building from Source
If you want to run the project from the source code, fix my AI's spaghetti logic, or modify it:

1. Clone the repository:
   ```bash
   git clone https://github.com
   cd osu-ai-coach
   ```
2. Create and activate a clean virtual environment:
   ```bash
   python -m venv venv
   # On Windows (CMD):
   venv\Scripts\activate.bat
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```bash
   pip install numpy osrparse pystray pillow watchdog pyinstaller
   ```
4. Compile your own `.exe`:
   ```bash
   pyinstaller --onefile --noconsole --clean --copy-metadata osrparse osu.py
   ```

## 📝 License & Contributing
This project is open-source. Since half of this was written by an AI and the other half by a human, it probably has some bugs. Feel free to fork it, submit issues, or open pull requests if you know how to make it better!

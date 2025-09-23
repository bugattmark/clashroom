# Society of Debaters — Web Speech Lean MVP

Minimal demo: two fake agents + you. Uses Chrome’s built-in Web Speech API.

Setup:
```powershell
cd agentSocSim-webspeech
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --reload
```

Open http://127.0.0.1:8000

- **Connect**: enable mic and STT.
- **Start debate**: Agent A starts, then B replies.
- Speak anytime: barge-in with STT.

Replace `fakeAgentRespond` in `public/app.js` with real API calls later.

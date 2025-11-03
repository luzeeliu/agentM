# AgentM Frontend

Open `frontend/index.html` in a browser, or serve the folder with any static server.

Configure backend URL:
- Defaults to `http://localhost:8000`.
- To override, define `window.API_BASE` before `script.js` or serve both under the same origin.

Usage:
- Enter text in the input or attach an image (or both), then click 发送.
- The UI posts to `/api/chat` and shows the agent response.

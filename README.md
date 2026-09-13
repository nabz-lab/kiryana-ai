# Kiryana AI 🛒
Hackathon MVP: an AI grocery-budget agent for Karachi households.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

For AI explanations, add `OPENAI_API_KEY` to Streamlit Secrets or your environment.
Optional: `OPENAI_MODEL`.

Prototype prices are estimated sample values, not live Karachi market prices.

## Streamlit Cloud
Deploy this repo, choose `app.py`, then add:
```toml
OPENAI_API_KEY = "your-key"
```
under App settings → Secrets.

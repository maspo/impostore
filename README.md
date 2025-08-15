
# L'Impostore – Mini Flask App

Applicazione minimale per giocare a "l'Impostore" da browser, con un Master e più giocatori che usano il telefono.

## Avvio locale

```bash
python -m venv venv
source venv/bin/activate  # su Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
# visita http://localhost:5000
```

## Deploy su Render (manuale)

1. Crea un nuovo repository su GitHub e carica questi file.
2. Su Render: **New +** → **Web Service** → collega il repo.
3. Impostazioni principali:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3.x (qualsiasi recente)
   - (Opzionale) **Environment Variable** `WORDS_FILE = words.txt`
4. Deploy! Condividi l'URL generato ai giocatori.

## Deploy su Render con `render.yaml`

Se preferisci IaC, mantieni `render.yaml` in repo. Su Render: **Blueprints** → collega il repo.


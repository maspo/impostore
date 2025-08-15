import os
import random
import string
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from flask import Flask, request, redirect, url_for, render_template, abort
from jinja2 import DictLoader
# ---------- Config ----------
WORDS_FILE = os.environ.get("WORDS_FILE", "words.txt")
MIN_PLAYERS = 3  # minimo consigliato per partire

app = Flask(__name__)
lock = threading.Lock()


def _token(n=10):
    # piccolo token per i giocatori, sufficiente per uso casual
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def load_words(path=WORDS_FILE):
    if not os.path.exists(path):
        # fallback di sicurezza
        return ["pizza", "montagna", "aereo", "computer", "mare", "biblioteca"]
    with open(path, "r", encoding="utf-8") as f:
        words = [w.strip() for w in f.readlines()]
    return [w for w in words if w]


@dataclass
class Player:
    name: str
    token: str
    is_master: bool = False


@dataclass
class RoundInfo:
    number: int = 0
    secret_word: Optional[str] = None
    impostor_token: Optional[str] = None


@dataclass
class GameState:
    players_by_token: Dict[str, Player] = field(default_factory=dict)
    master_token: Optional[str] = None
    current_round: RoundInfo = field(default_factory=RoundInfo)

    def reset_all(self):
        self.players_by_token.clear()
        self.master_token = None
        self.current_round = RoundInfo()

    def start_new_round(self):
        if len(self.players_by_token) < MIN_PLAYERS:
            raise ValueError(f"Servono almeno {MIN_PLAYERS} giocatori per iniziare.")
        self.current_round.number += 1
        self.current_round.secret_word = random.choice(load_words())
        self.current_round.impostor_token = random.choice(list(self.players_by_token.keys()))


STATE = GameState()


# ---------- TEMPLATES ----------
BASE = """
<!doctype html>
<html lang="it">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>L’Impostore – Mini App</title>
    <style>
      :root{--bg:#0f172a;--card:#111827;--muted:#cbd5e1;--text:#e5e7eb;--accent:#22c55e;--danger:#ef4444}
      body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial}
      .wrap{max-width:720px;margin:24px auto;padding:16px}
      .card{background:var(--card);border-radius:16px;padding:20px;box-shadow:0 8px 30px rgba(0,0,0,0.25)}
      h1,h2,h3{margin:0 0 12px}
      .muted{color:var(--muted)}
      input[type=text]{width:100%;padding:12px;border-radius:12px;border:1px solid #374151;background:#0b1220;color:var(--text)}
      label{display:block;margin:10px 0}
      .row{display:flex;gap:8px;flex-wrap:wrap}
      .btn{appearance:none;border:none;border-radius:12px;padding:10px 14px;cursor:pointer}
      .btn.primary{background:var(--accent);color:#06210f}
      .btn.danger{background:var(--danger);color:#fff}
      .pill{display:inline-block;background:#0b1220;border:1px solid #374151;padding:6px 10px;border-radius:999px;margin:4px 6px 0 0}
      .grid{display:grid;gap:12px}
      .center{text-align:center}
      .word{font-size:40px;font-weight:800;letter-spacing:1px}
      .imp{font-size:40px;font-weight:800;color:var(--danger)}
      small{opacity:.8}
      a{color:#93c5fd}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        {% block content %}{% endblock %}
      </div>
      <p class="muted" style="margin-top:12px"><small>Minimal Flask app – nessun login, una sola partita globale.</small></p>
    </div>
  </body>
</html>
"""

HOME = """
{% extends "BASE" %}
{% block content %}
<h1>L’Impostore</h1>
<p class="muted">Inserisci il nome. Se sei il Master, spunta la casella.</p>
<form method="post" action="{{ url_for('join') }}" class="grid">
  <label>Nome
    <input type="text" name="name" required maxlength="40" placeholder="Es. Chiara">
  </label>
  <label><input type="checkbox" name="is_master"> Sono il Master</label>
  <div class="row">
    <button class="btn primary" type="submit">Entra</button>
    <a class="btn" href="{{ url_for('status') }}">Vedi stato</a>
  </div>
</form>
{% if players %}
  <hr>
  <h3>Giocatori connessi</h3>
  {% for p in players %}
    <span class="pill">{{ p.name }}{% if p.is_master %} • Master{% endif %}</span>
  {% endfor %}
{% endif %}
{% endblock %}
"""

MASTER = """
{% extends "BASE" %}
{% block content %}
<h1>Area Master</h1>
<p class="muted">Condividi ai giocatori il link <code>{{ base_url }}</code> per entrare.</p>

<h3>Giocatori ({{ players|length }})</h3>
<div>
  {% for p in players %}
    <span class="pill">{{ p.name }}</span>
  {% endfor %}
</div>

<hr>
<h3>Turno</h3>
<p>Numero turno: <strong>{{ round.number }}</strong>{% if round.secret_word %} • Parola selezionata{% endif %}</p>
<div class="row">
  <form method="post" action="{{ url_for('start_round') }}">
    <button class="btn primary" type="submit">Nuovo turno</button>
  </form>
  <form method="post" action="{{ url_for('reset_game') }}" onsubmit="return confirm('Sei sicuro? Tutto andrà perso.')">
    <button class="btn danger" type="submit">Reset partita</button>
  </form>
</div>

{% if round.secret_word %}
  <div class="card" style="margin-top:16px">
    <p class="muted">Anteprima (solo per il Master)</p>
    <p>Parola segreta: <strong>{{ round.secret_word }}</strong></p>
    <p>Impostore: <strong>{{ imp_name }}</strong></p>
  </div>
{% endif %}
{% endblock %}
"""

PLAYER = """
{% extends "BASE" %}
{% block content %}
<h1>Ciao {{ player.name }} 👋</h1>
<p class="muted">Quando il Master avvia un turno, qui comparirà la tua informazione.</p>

{% if round.number == 0 %}
  <p class="center">In attesa che il Master inizi…</p>
{% else %}
  {% if is_impostor %}
    <p class="center imp">SEI L’IMPOSTORE 😈</p>
    <p class="center">Fingi di conoscere la parola…</p>
  {% else %}
    <p class="center muted">La parola segreta è:</p>
    <p class="center word">{{ round.secret_word }}</p>
  {% endif %}
  <p class="center"><small>Turno #{{ round.number }}</small></p>
{% endif %}

<div class="center" style="margin-top:12px">
  <a class="btn" href="{{ url_for('player', token=player.token) }}">Aggiorna</a>
</div>
{% endblock %}
"""

STATUS = """
{% extends "BASE" %}
{% block content %}
<h1>Stato partita</h1>
<p>Giocatori ({{ players|length }}): {% for p in players %}<span class="pill">{{ p.name }}</span>{% endfor %}</p>
<p>Turno attuale: <strong>{{ round.number }}</strong>{% if round.secret_word %} • parola selezionata{% endif %}</p>
<p><a href="{{ url_for('home') }}">Torna alla home</a></p>
{% endblock %}
"""

# Register template strings
TEMPLATES = {"BASE": BASE, "HOME": HOME, "MASTER": MASTER, "PLAYER": PLAYER, "STATUS": STATUS}
app.jinja_loader = DictLoader(TEMPLATES)

def render(name, **ctx):
    return render_template(name, **ctx)

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def home():
    with lock:
        players = list(STATE.players_by_token.values())
    return render("HOME", players=players)


@app.route("/join", methods=["POST"])
def join():
    name = (request.form.get("name") or "").strip()
    is_master = bool(request.form.get("is_master"))
    if not name:
        return redirect(url_for("home"))

    token = _token()
    with lock:
        p = Player(name=name, token=token, is_master=is_master)
        STATE.players_by_token[token] = p
        if is_master:
            STATE.master_token = token
    # Vai alla pagina giusta
    if is_master:
        return redirect(url_for("master", token=token))
    else:
        return redirect(url_for("player", token=token))


@app.route("/master/<token>", methods=["GET"])
def master(token):
    with lock:
        if token != STATE.master_token or token not in STATE.players_by_token:
            abort(403)
        players = list(STATE.players_by_token.values())
        rnd = STATE.current_round
        imp_name = None
        if rnd.impostor_token and rnd.impostor_token in STATE.players_by_token:
            imp_name = STATE.players_by_token[rnd.impostor_token].name
    base_url = request.host_url.rstrip("/")
    return render("MASTER", players=players, round=rnd, base_url=base_url, imp_name=imp_name)


@app.route("/player/<token>", methods=["GET"])
def player(token):
    with lock:
        player = STATE.players_by_token.get(token)
        if not player:
            abort(404)
        rnd = STATE.current_round
        is_imp = (rnd.impostor_token == token and rnd.number > 0)
    return render("PLAYER", player=player, round=rnd, is_impostor=is_imp)


@app.route("/status", methods=["GET"])
def status():
    with lock:
        players = list(STATE.players_by_token.values())
        rnd = STATE.current_round
    return render("STATUS", players=players, round=rnd)


@app.route("/start", methods=["POST"])
def start_round():
    # solo master
    token = request.args.get("token") or request.form.get("token") or request.referrer.split("/")[-1]
    with lock:
        if token != STATE.master_token:
            abort(403)
        try:
            STATE.start_new_round()
        except ValueError as e:
            return f"<p style='font-family:system-ui'>Errore: {e}<br><a href='{url_for('master', token=token)}'>Torna indietro</a></p>"
    return redirect(url_for("master", token=token))


@app.route("/reset", methods=["POST"])
def reset_game():
    token = request.args.get("token") or request.form.get("token") or request.referrer.split("/")[-1]
    with lock:
        if token != STATE.master_token:
            abort(403)
        STATE.reset_all()
    return redirect(url_for("home"))


# comodo alias per i form del template master
@app.route("/start_round", methods=["POST"])
def start_round_alias():
    # manteniamo il token dalla referrer
    return start_round()


@app.route("/reset_game", methods=["POST"])
def reset_game_alias():
    return reset_game()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)

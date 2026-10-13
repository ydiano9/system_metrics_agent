# System Metrics Agent — chaîne DevSecOps

Agent Python qui collecte CPU, RAM et charge système (`psutil` + commande
`uptime`) et les envoie à une API FastAPI. Ce fork ajoute la
conteneurisation, un pipeline CI/CD sécurisé et un monitoring
Prometheus + Grafana.

> **Liens à compléter :**
> Fork : `https://github.com/<vous>/system_metrics_agent` ·
> Images : `https://hub.docker.com/r/<vous>/system-metrics-api` et
> `https://hub.docker.com/r/<vous>/system-metrics-agent` ·
> Pipeline vert : `<lien du run>` · Pipeline rouge : `<lien du run>`

## Rapport

**Correctifs de prise en main.** Les tests sont dans `app/tests/` et non
`tests/` comme l'indiquait l'ancien README, et `test_api.py` n'existait pas :
il a été ajouté (avec des tests de `config.py` et `agent.py`). Le fichier
mort `app/montFichier.py` (import inutilisé, cassait flake8) a été supprimé.
Les dépendances sont maintenant figées et séparées : `requirements-api.txt`,
`requirements-agent.txt` (exécution) et `requirements-dev.txt` (tests, lint).

**Choix Docker.** Image `python:3.12.15-slim-trixie` : tag précis pour des
builds reproductibles, slim (glibc) pour garder les wheels `psutil`
précompilées, contrairement à alpine (musl) qui impose de compiler.
Build **multi-stage** : les dépendances sont installées dans un venv
(`/opt/venv`) à l'étape builder, puis seul ce venv et le code sont copiés.
`requirements` copié avant le code (cache), `pip --no-cache-dir`,
`.dockerignore` strict, tests retirés de l'image. Utilisateur **non-root**
(uid 10001), aucun `.env` ni secret dans l'image, configuration injectée par
variables d'environnement. API : `uvicorn` sans `--reload`, `--host 0.0.0.0`,
`EXPOSE 8000`, `HEALTHCHECK` en Python (pas de `curl` dans slim).

**Commande `uptime`.** Absente de l'image slim, elle est fournie par le
paquet Debian `procps`, ajouté à l'image de l'agent uniquement
(`--no-install-recommends`, listes apt supprimées).

**Conteneur et hôte.** Dans un conteneur, `psutil` lit le `/proc` du
conteneur : le hostname est l'ID du conteneur et le CPU/RAM reflètent ses
limites (cgroups), pas la machine. Pour surveiller un vrai serveur, il faut
lancer l'agent avec `pid: host` et monter `/proc` de l'hôte en lecture seule,
ou l'installer directement sur l'hôte (service systemd).

**Tailles d'images** (`docker images`) : API `___ Mo`, agent `___ Mo`.

**Monitoring (ajout).** L'API expose `GET /prometheus` (format Prometheus) :
CPU, RAM, charge et date du dernier envoi de chaque agent. Prometheus la
scrape toutes les 10 s et évalue 4 alertes : `ApiDown`, `AgentSilent`
(aucune donnée depuis 30 s), `HighCpuUsage` (> 85 %), `HighMemoryUsage`
(> 90 %). Grafana est provisionné automatiquement (source + tableau de bord).

**Échec volontaire.** `<décrire : image de base ancienne, Trivy rouge, push
bloqué, puis correction>`

**Difficultés rencontrées.** `<à compléter>`

## Lancer en local

```bash
cp .env.example .env          # puis modifier GRAFANA_ADMIN_PASSWORD
docker compose up --build     # API + agent
curl http://localhost:8000/metrics/latest
```

Avec le monitoring :

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up --build
```

| Service    | URL                                   |
| ---------- | ------------------------------------- |
| API (docs) | http://localhost:8000/docs            |
| Prometheus | http://localhost:9090 (onglet Alerts) |
| Grafana    | http://localhost:3000                 |

Hors conteneur (Python 3.11+) :

```bash
pip install -r requirements-dev.txt
uvicorn app.api:app                       # terminal 1
METRICS_ENDPOINT=http://127.0.0.1:8000/metrics python -m app.agent   # terminal 2
pytest -q --cov=app
```

## Endpoints

| Méthode | Chemin            | Rôle                               |
| ------- | ----------------- | ---------------------------------- |
| GET     | `/health`         | État de l'API                      |
| POST    | `/metrics`        | Réception d'une métrique (agent)   |
| GET     | `/metrics`        | Historique (1000 dernières)        |
| GET     | `/metrics/latest` | Dernière métrique reçue            |
| GET     | `/prometheus`     | Métriques au format Prometheus     |

## Pipeline CI/CD (`.github/workflows/ci-cd.yml`)

1. **test** : black + flake8, `pytest --cov`, analyse SonarQube, Quality Gate
   bloquante.
2. **build-scan-push** (`needs: test`, matrice `api` / `agent`) : build
   `load: true`, scan Trivy bloquant (HIGH/CRITICAL corrigeables), rapport
   SARIF dans l'onglet Security, push `:<sha>` et `:latest` uniquement sur
   `main`. Cache Buildx `type=gha`. Dependabot met à jour pip, Docker et
   les actions.

Secrets GitHub requis : `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (Access
Token), `SONAR_TOKEN`, `SONAR_HOST_URL`.

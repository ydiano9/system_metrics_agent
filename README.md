# System Metrics Agent — chaîne DevSecOps

Agent Python qui collecte CPU, RAM et charge système (`psutil` + commande
`uptime`) et les envoie à une API FastAPI. Ce fork ajoute la
conteneurisation, un pipeline CI/CD sécurisé et un monitoring
Prometheus + Grafana.

**Liens :**
- Fork : https://github.com/ydiano9/system_metrics_agent
- Image API : https://hub.docker.com/r/yombi99/system-metrics-api
- Image agent : https://hub.docker.com/r/yombi99/system-metrics-agent
- Exécutions du pipeline (vertes, et la rouge volontaire n°3) :
  https://github.com/ydiano9/system_metrics_agent/actions

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

**Tailles d'images** (compressées, Docker Hub) : API **50,34 Mo**, agent
**46,79 Mo**. L'API est la plus lourde car FastAPI, Uvicorn et Pydantic
pèsent plus que `psutil` + `requests` + `procps`. Tags publiés : `latest`
et le SHA du commit.

**Monitoring (ajout).** L'API expose `GET /prometheus` (format Prometheus) :
CPU, RAM, charge et date du dernier envoi de chaque agent. Prometheus la
scrape toutes les 10 s et évalue 4 alertes : `ApiDown`, `AgentSilent`
(aucune donnée depuis 30 s), `HighCpuUsage` (> 85 %), `HighMemoryUsage`
(> 90 %). Grafana est provisionné automatiquement (source + tableau de bord).

**Échec volontaire.** Un test a été cassé exprès sur `main`
(`/health` attendu à `"ko"`). Le job `test` a échoué, le job
`build-scan-push` a donc été sauté : aucune image n'a été poussée. Le test a
ensuite été corrigé et le pipeline est redevenu vert.

**Difficultés rencontrées.**
- Pipeline bloqué au démarrage : les annotations du job indiquaient un
  compte GitHub verrouillé pour un problème de facturation. Le dépôt a été
  migré vers un autre compte.
- Push refusé : un jeton GitHub sans la permission `workflow` ne peut pas
  modifier `.github/workflows/`. Il a fallu un jeton avec `repo` + `workflow`.
- Erreurs de nommage de secrets (`DOCKER_TOKEN` au lieu de
  `DOCKERHUB_TOKEN`) : le nom doit correspondre exactement au workflow.

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

## Endpoints

| Méthode | Chemin            | Rôle                             |
| ------- | ----------------- | -------------------------------- |
| GET     | `/health`         | État de l'API                    |
| POST    | `/metrics`        | Réception d'une métrique (agent) |
| GET     | `/metrics`        | Historique (1000 dernières)      |
| GET     | `/metrics/latest` | Dernière métrique reçue          |
| GET     | `/prometheus`     | Métriques au format Prometheus   |

## Pipeline CI/CD (`.github/workflows/ci-cd.yml`)

1. **test** : black + flake8, `pytest --cov`, analyse SonarQube, Quality Gate
   bloquante.
2. **build-scan-push** (`needs: test`, matrice `api` / `agent`) : build
   `load: true`, scan Trivy bloquant (HIGH/CRITICAL corrigeables), rapport
   SARIF dans l'onglet Security, push `:<sha>` et `:latest` uniquement sur
   `main`. Cache Buildx `type=gha`.

Secrets GitHub requis : `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`,
`SONAR_TOKEN`, `SONAR_HOST_URL`.

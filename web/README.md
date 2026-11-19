# Interface Lighthouse Lab

Le navigateur appelle une API HTTP Python. L’API utilise
`core.rag.pipeline.RAGPipeline`, également utilisé par la CLI.

## Lancement local

Avec PostgreSQL et Ollama démarrés, depuis la racine du dépôt :

```sh
venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Puis, dans un second terminal :

```sh
cd web
export PATH="$PWD/.tools/node/bin:$PATH"
npm run dev
```

Ouvre l’URL affichée par Vite, saisis une question et clique sur **Send**.
Ouvre **Sources** sous une réponse pour consulter les extraits sur place.
Le panneau latéral indique les documents d’origine et leurs noms de fichiers. **New chat** démarre une autre conversation. La
navigation permet de retrouver les conversations de l’onglet courant jusqu’à
son actualisation.

Pour préparer une nouvelle installation, installe les dépendances Python
depuis `requirements.txt` dans le venv du projet, puis lance `npm ci` dans
`web/` avec Node.js 22.12 ou une version ultérieure compatible avec Vite 7.
`npm run build` vérifie les types et produit les fichiers statiques.

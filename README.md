# Gradio Tunnel Dashboard

Dashboard web per un server Linux che individua le porte in ascolto, permette di avviare e fermare tunnel tramite `gradio-tunneling` e mostra l'URL generato.

## Avvio rapido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Apri `http://localhost:8000`.

## Configurazione

Il comando usato per avviare i tunnel è configurabile con la variabile d'ambiente `TUNNEL_COMMAND`.

Esempio:

```bash
export TUNNEL_COMMAND="python -m gradio_tunneling --port {port}"
```

L'URL viene rilevato dalla prima stringa che contiene un link HTTP/HTTPS nel log del tunnel.

La dashboard aggiorna automaticamente lo stato dei tunnel e mostra l'ultimo log per aiutare il debug
quando l'URL non è disponibile.

## Debug

Nella sezione dei tunnel puoi aprire il pannello Log per vedere le ultime righe prodotte dal processo
`gradio_tunneling`. Questo aiuta a capire se il tunnel non parte o se l'URL non viene stampato.

## Rilevamento servizi Docker

La tabella delle porte mostra anche il nome del container Docker quando disponibile. Questo richiede
che il processo abbia accesso al socket Docker locale.

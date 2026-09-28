# Scraper de resultados de Baloto

Descarga el histórico de resultados de [baloto.com](https://baloto.com) para
**Baloto**, **Revancha**, **MiLoto** y **ColorLOTO**.

```bash
pip install -r requirements.txt
python scraper_baloto.py
```

Genera `baloto.csv`, `revancha.csv`, `miloto.csv`, `colorloto.csv` y
`resultados_baloto.xlsx` (una hoja por juego). Espera `PAUSA` segundos entre
páginas para no saturar el sitio.

El parser depende del HTML actual del sitio (enlaces "Ver detalle", fechas tipo
"12 de marzo de 2025" y el texto "Página X de N" para la paginación). Si el
sitio cambia su estructura, el script avisa cuando no encuentra sorteos.

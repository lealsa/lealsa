"""
Scraper del histórico de resultados de baloto.com
Juegos: Baloto, Revancha, MiLoto y ColorLOTO.

Requisitos:
    pip install -r requirements.txt

Uso:
    python scraper_baloto.py
Genera: baloto.csv, revancha.csv, miloto.csv, colorloto.csv y resultados_baloto.xlsx
"""
import re
import time
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PAUSA = 1.0  # segundos entre peticiones, para no saturar el sitio

SECCIONES = {
    # nombre: URL base del histórico (acepta ?page=N)
    "baloto_revancha": "https://baloto.com/resultados",
    "miloto": "https://baloto.com/miloto/resultados/",
    "colorloto": "https://baloto.com/colorloto/resultados",
}

# El enlace "Ver detalle" identifica juego y número de sorteo
PATRONES_LINK = [
    (re.compile(r"/resultados-baloto/(\d+)"), "Baloto"),
    (re.compile(r"/resultados-revancha/(\d+)"), "Revancha"),
    (re.compile(r"/miloto/resultados-miloto/(\d+)"), "MiLoto"),
    (re.compile(r"/colorloto/resultados/(\d+)"), "ColorLOTO"),
]

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}
RE_FECHA = re.compile(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(\d{4})")
RE_TOTAL_PAG = re.compile(r"P[áa]gina\s+\d+\s+de\s+(\d+)", re.I)
RE_NUM = re.compile(r"\d{1,2}")
TAGS_BOLA = ["b", "strong", "span", "div"]

session = requests.Session()
session.headers.update(HEADERS)


def descargar(url, intentos=4):
    for i in range(intentos):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            espera = 2 ** (i + 1)
            print(f"  Error en {url}: {e}. Reintento en {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar {url}")


def parsear_fecha(texto):
    m = RE_FECHA.search(texto)
    if not m:
        return None
    d, mes, a = m.groups()
    mes_num = MESES.get(mes.lower())
    return date(int(a), mes_num, int(d)) if mes_num else None


def color_de(tag):
    """ColorLOTO: intenta extraer el color de la balota desde clases o estilos."""
    for t in (tag, tag.parent):
        if t is None:
            continue
        clases = " ".join(t.get("class", []))
        estilo = t.get("style", "")
        if clases or estilo:
            return (clases + " " + estilo).strip()
    return ""


def bolas_colorloto(celdas):
    """Balotas de ColorLOTO: solo el tag más interno con el número, para no
    contar dos veces un <div><span>7</span></div>."""
    bolas = []
    for td in celdas:
        for b in td.find_all(TAGS_BOLA):
            if not RE_NUM.fullmatch(b.get_text(strip=True)):
                continue
            if any(RE_NUM.fullmatch(h.get_text(strip=True)) for h in b.find_all(TAGS_BOLA)):
                continue  # un descendiente ya contiene el mismo número
            bolas.append(b)
    return bolas


def parsear_pagina(html):
    soup = BeautifulSoup(html, "html.parser")
    filas = []
    for tr in soup.find_all("tr"):
        a = tr.find("a", href=True)
        if not a:
            continue
        juego = sorteo = None
        for patron, nombre in PATRONES_LINK:
            m = patron.search(a["href"])
            if m:
                juego, sorteo = nombre, int(m.group(1))
                break
        if not juego:
            continue

        celdas = tr.find_all("td")
        fecha = next((f for td in celdas
                      if (f := parsear_fecha(td.get_text(" ", strip=True)))), None)
        fila = {"juego": juego, "sorteo": sorteo, "fecha": fecha}

        if juego == "ColorLOTO":
            for i, b in enumerate(bolas_colorloto(celdas), 1):
                fila[f"numero_{i}"] = int(b.get_text(strip=True))
                fila[f"color_{i}"] = color_de(b)
        else:
            nums = []
            for td in celdas:
                txt = td.get_text(" ", strip=True)
                if re.fullmatch(r"\d{1,2}(\s*-\s*\d{1,2})+", txt):
                    nums = [int(n) for n in RE_NUM.findall(txt)]
                    break
            if juego in ("Baloto", "Revancha"):
                for i, n in enumerate(nums[:5], 1):
                    fila[f"n{i}"] = n
                fila["superbalota"] = nums[5] if len(nums) > 5 else None
            else:
                for i, n in enumerate(nums, 1):
                    fila[f"n{i}"] = n
        filas.append(fila)

    m = RE_TOTAL_PAG.search(soup.get_text(" ", strip=True))
    total = int(m.group(1)) if m else 1
    return filas, total


def scrapear_seccion(nombre, base):
    print(f"\n== {nombre} ==")
    filas, total = parsear_pagina(descargar(base))
    print(f"  Página 1/{total}: {len(filas)} filas")
    sep = "&" if "?" in base else "?"
    for p in range(2, total + 1):
        time.sleep(PAUSA)
        nuevas, _ = parsear_pagina(descargar(f"{base}{sep}page={p}"))
        filas.extend(nuevas)
        print(f"  Página {p}/{total}: {len(nuevas)} filas")
    return filas


def main():
    todas = []
    for nombre, url in SECCIONES.items():
        todas.extend(scrapear_seccion(nombre, url))

    if not todas:
        print("\nNo se encontraron sorteos: revisa si cambió el HTML del sitio.")
        return

    df = pd.DataFrame(todas).drop_duplicates(subset=["juego", "sorteo"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    with pd.ExcelWriter("resultados_baloto.xlsx") as xls:
        for juego, sub in df.groupby("juego"):
            sub = sub.dropna(axis=1, how="all").sort_values("sorteo")
            num_cols = [c for c in sub.columns if re.fullmatch(r"n\d+|numero_\d+|superbalota", c)]
            sub[num_cols] = sub[num_cols].astype("Int64")  # enteros aunque haya vacíos
            sub.to_csv(f"{juego.lower()}.csv", index=False, encoding="utf-8-sig",
                       date_format="%Y-%m-%d")
            sub.to_excel(xls, sheet_name=juego, index=False)
            fechas = sub["fecha"].dropna() if "fecha" in sub else pd.Series(dtype="datetime64[ns]")
            rango = (f"{fechas.min():%Y-%m-%d} → {fechas.max():%Y-%m-%d}"
                     if len(fechas) else "sin fechas")
            print(f"{juego}: {len(sub)} sorteos ({rango})")
    print("\nListo: CSVs por juego + resultados_baloto.xlsx")


if __name__ == "__main__":
    main()

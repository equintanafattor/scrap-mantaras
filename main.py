from pathlib import Path
import time
import re

import pandas as pd
from playwright.sync_api import sync_playwright

ARCHIVO_SALIDA = "expedientes_pjn_detalle.xlsx"
MAX_FILAS_POR_PAGINA = None  # None = todas
MAX_PAGINAS_POR_EJECUCION = 63
SOLO_COMPLETAR_VACIOS = True


def limpiar(texto: str) -> str:
    return " ".join(texto.replace("\n", " ").split())


def extraer_primera_actuacion(texto: str) -> str:
    patron = re.search(
        r"Oficina:\s*(.*?)\s*Fecha:\s*(.*?)\s*Tipo actuacion:\s*(.*?)\s*(?:Descripcion|Descripción|Detalle):\s*(.*?)(?=\s*Oficina:|\s*Descargar|\s*Ver|\s*Contáctenos|$)",
        texto,
        re.IGNORECASE,
    )

    if not patron:
        return ""

    fecha = patron.group(2).strip()
    tipo = patron.group(3).strip()
    descripcion = patron.group(4).strip()

    descripcion = descripcion.replace("Descargar Ver", "").strip()

    return f"{fecha}: {tipo} - {descripcion}".strip()


def obtener_ultimo_movimiento(page) -> str:
    page.wait_for_timeout(2500)
    texto = limpiar(page.inner_text("body"))

    if "El expediente no posee actuaciones actuales" in texto:
        page.get_by_text("Ver históricas").click()
        page.wait_for_timeout(2500)
        texto = limpiar(page.inner_text("body"))
        return extraer_primera_actuacion(texto)

    tablas = page.locator("table")

    for i in range(tablas.count()):
        tabla_texto = limpiar(tablas.nth(i).inner_text())

        if "OFICINA" in tabla_texto and "FECHA" in tabla_texto and "TIPO" in tabla_texto:
            filas = tablas.nth(i).locator("tr")

            for j in range(1, filas.count()):
                celdas = filas.nth(j).locator("td")

                if celdas.count() >= 4:
                    valores = []

                    for k in range(celdas.count()):
                        valor = limpiar(celdas.nth(k).inner_text())

                        if not valor:
                            continue

                        if valor in ["Descargar", "Ver"]:
                            continue

                        valores.append(valor)

                    texto_fila = " ".join(valores)

                    # Caso accesible: Oficina: ... Fecha: ... Tipo actuacion: ... Descripcion: ...
                    if "Oficina:" in texto_fila and "Fecha:" in texto_fila:
                        movimiento = extraer_primera_actuacion(texto_fila)
                        if movimiento:
                            return movimiento

                    # Caso tabla normal: oficina, fecha, tipo, descripcion, a fs
                    fecha_idx = None

                    for idx, valor in enumerate(valores):
                        if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", valor):
                            fecha_idx = idx
                            break

                    if fecha_idx is not None and len(valores) > fecha_idx + 2:
                        fecha = valores[fecha_idx]
                        tipo = valores[fecha_idx + 1]
                        descripcion = valores[fecha_idx + 2]

                        return f"{fecha}: {tipo} - {descripcion}".strip()
    
    print("\nDEBUG: no pude extraer movimiento.")
    print("URL:", page.url)
    print(limpiar(page.inner_text("body"))[:4000])
    input("Revisá esta pantalla y presioná ENTER para continuar...")

    return ""


def esta_en_lista(page) -> bool:
    texto = limpiar(page.inner_text("body"))
    return "Lista de Expedientes Relacionados" in texto and "visualizar expediente" in texto


def volver_a_lista(page):
    for _ in range(8):
        if esta_en_lista(page):
            return

        links = page.locator("a, button")

        for i in range(links.count()):
            texto = limpiar(links.nth(i).inner_text())

            if texto in ["Volver a Mi Lista", "Volver al expediente"]:
                print("Click volver:", texto)
                links.nth(i).click()
                page.wait_for_timeout(2500)
                break
        else:
            page.wait_for_timeout(1000)

    raise Exception("No pude volver a la lista")


def cargar_existentes() -> pd.DataFrame:
    if Path(ARCHIVO_SALIDA).exists():
        df = pd.read_excel(ARCHIVO_SALIDA)

        if "Error" not in df.columns:
            df["Error"] = ""

        return df

    return pd.DataFrame(
        columns=[
            "Número de expediente",
            "Juzgado",
            "Carátula",
            "Situación",
            "Últ. Act. listado",
            "Último movimiento",
            "Error",
        ]
    )


def guardar(df: pd.DataFrame):
    salida = Path(ARCHIVO_SALIDA).resolve()
    print(f"Guardando en: {salida}")

    df.to_excel(salida, index=False)
    df.to_csv(
        salida.with_suffix(".csv"),
        index=False,
        encoding="utf-8-sig",
    )


def click_siguiente_si_existe(page):
    links = page.locator("a")

    for i in range(links.count()):
        onclick = links.nth(i).get_attribute("onclick") or ""
        texto = limpiar(links.nth(i).inner_text())

        # El botón siguiente no tiene texto
        if "j_idt292" in onclick:
            print("\nPasando a la siguiente página...")
            links.nth(i).click()
            page.wait_for_timeout(3000)
            return True

    return False


def main():
    df = cargar_existentes()
    df["Número de expediente"] = df["Número de expediente"].astype(str).str.strip()

    if SOLO_COMPLETAR_VACIOS:
        pendientes = set(
            df[
                df["Último movimiento"].isna()
                | (df["Último movimiento"].astype(str).str.strip() == "")
            ]["Número de expediente"]
        )

        print(f"Modo completar vacíos activo. Pendientes: {len(pendientes)}")
        procesados = set()
    else:
        pendientes = set()
        procesados = set(df["Número de expediente"].dropna().astype(str).str.strip())

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        print("\nPestañas abiertas:")
        for idx, page in enumerate(context.pages):
            print(f"{idx}: {page.url}")

        opcion = int(input("\nNúmero de pestaña con Lista de Expedientes Relacionados: "))
        page = context.pages[opcion]
        page.bring_to_front()

        pagina = 1

        while True:
            print(f"\n=== Página {pagina} ===")

            tabla_expedientes = page.locator("table").nth(5)
            rows = tabla_expedientes.locator("tr")
            total_filas = rows.count()

            limite = total_filas
            if MAX_FILAS_POR_PAGINA is not None:
                limite = min(total_filas, MAX_FILAS_POR_PAGINA + 1)

            for i in range(1, limite):
                tabla_expedientes = page.locator("table").nth(5)
                row = tabla_expedientes.locator("tr").nth(i)
                cells = row.locator("td")

                if cells.count() < 6:
                    continue

                expediente = limpiar(cells.nth(0).inner_text())
                if SOLO_COMPLETAR_VACIOS and expediente not in pendientes:
                    print("No pendiente, salto:", expediente)
                    continue

                if not expediente or expediente in procesados:
                    print("Ya procesado, salto:", expediente)
                    continue

                dependencia = limpiar(cells.nth(1).inner_text())
                caratula = limpiar(cells.nth(2).inner_text())
                situacion = limpiar(cells.nth(3).inner_text())
                ultima_act_listado = limpiar(cells.nth(4).inner_text())

                print(f"\nProcesando: {expediente}")

                ojo = row.locator("i.fa-eye").locator("xpath=ancestor::a[1]")

                if ojo.count() == 0:
                    print("No encontré ojo:", expediente)
                    continue

                try:
                    ojo.first.click()
                    ultimo_movimiento = obtener_ultimo_movimiento(page)

                    if SOLO_COMPLETAR_VACIOS:
                        idx = df.index[df["Número de expediente"] == expediente]

                        if len(idx) > 0:
                            if SOLO_COMPLETAR_VACIOS:
                                idx = df.index[
                                    (df["Número de expediente"].astype(str).str.strip() == expediente)
                                    & (
                                        df["Último movimiento"].isna()
                                        | (df["Último movimiento"].astype(str).str.strip() == "")
                                    )
                                ]

                                print("Movimiento obtenido:", ultimo_movimiento)
                                print("Filas a actualizar:", len(idx))

                                if len(idx) > 0 and ultimo_movimiento.strip():
                                    df.loc[idx, "Último movimiento"] = ultimo_movimiento
                                    df.loc[idx, "Error"] = ""
                                    pendientes.discard(expediente)
                                else:
                                    df.loc[idx, "Error"] = "No se pudo obtener último movimiento"
                            df.loc[idx[0], "Error"] = ""
                    else:
                        nueva_fila = {
                            "Número de expediente": expediente,
                            "Juzgado": dependencia,
                            "Carátula": caratula,
                            "Situación": situacion,
                            "Últ. Act. listado": ultima_act_listado,
                            "Último movimiento": ultimo_movimiento,
                            "Error": "",
                        }

                        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
                        procesados.add(expediente)

                    guardar(df)
                    print(f"Guardado OK. Total actual: {len(df)}")

                    volver_a_lista(page)

                except Exception as e:
                    print(f"ERROR en {expediente}: {e}")

                    nueva_fila = {
                        "Número de expediente": expediente,
                        "Juzgado": dependencia,
                        "Carátula": caratula,
                        "Situación": situacion,
                        "Últ. Act. listado": ultima_act_listado,
                        "Último movimiento": "",
                        "Error": str(e),
                    }

                    df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
                    procesados.add(expediente)
                    guardar(df)

                    input("Revisá el navegador, volvé manualmente a la lista y presioná ENTER...")

                time.sleep(2)
            
            links = page.locator("a, button")

            print("\nLINKS/BOTONES:")
            for i in range(links.count()):
                texto = limpiar(links.nth(i).inner_text())
                href = links.nth(i).get_attribute("href")
                onclick = links.nth(i).get_attribute("onclick")

                if texto or onclick:
                    print("----")
                    print("idx:", i)
                    print("texto:", texto)
                    print("href:", href)
                    print("onclick:", onclick)

            if pagina >= MAX_PAGINAS_POR_EJECUCION:
                print(f"\nCorte programado: se procesaron {MAX_PAGINAS_POR_EJECUCION} páginas.")
                break

            if not click_siguiente_si_existe(page):
                break

            pagina += 1

        print(f"\nListo. Total acumulado: {len(df)} expedientes.")
        print(f"Archivo generado: {ARCHIVO_SALIDA}")

        browser.close()


if __name__ == "__main__":
    main()
from pathlib import Path
import time

import pandas as pd
from playwright.sync_api import sync_playwright

ARCHIVO_SALIDA = "expedientes_pjn_detalle.xlsx"
MAX_FILAS_POR_PAGINA = None  # None = todas
MAX_PAGINAS_POR_EJECUCION = 30


def limpiar(texto: str) -> str:
    return " ".join(texto.replace("\n", " ").split())


def extraer_primera_actuacion(texto: str) -> str:
    partes = texto.split("Oficina:")

    if len(partes) < 2:
        return ""

    primera = "Oficina:" + partes[1]

    fecha = ""
    tipo = ""
    descripcion = ""

    if "Fecha:" in primera and "Tipo actuacion:" in primera:
        fecha = primera.split("Fecha:")[1].split("Tipo actuacion:")[0].strip()

    if "Tipo actuacion:" in primera and "Descripcion:" in primera:
        tipo = primera.split("Tipo actuacion:")[1].split("Descripcion:")[0].strip()

    if "Descripcion:" in primera:
        descripcion = primera.split("Descripcion:")[1]
        descripcion = descripcion.split("Oficina:")[0].strip()
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
                    fecha = limpiar(celdas.nth(1).inner_text())
                    tipo = limpiar(celdas.nth(2).inner_text())
                    descripcion = limpiar(celdas.nth(3).inner_text())

                    if fecha:
                        return f"{fecha}: {tipo} - {descripcion}".strip()

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
        return pd.read_excel(ARCHIVO_SALIDA)

    return pd.DataFrame(
        columns=[
            "Número de expediente",
            "Juzgado",
            "Carátula",
            "Situación",
            "Últ. Act. listado",
            "Último movimiento",
        ]
    )


def guardar(df: pd.DataFrame):
    df.to_excel(ARCHIVO_SALIDA, index=False)
    df.to_csv(
        ARCHIVO_SALIDA.replace(".xlsx", ".csv"),
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
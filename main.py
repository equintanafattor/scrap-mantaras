from playwright.sync_api import sync_playwright
import pandas as pd

URL = "https://scw.pjn.gov.ar/scw/expediente.seam"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        page.goto(URL)

        input("Logueate, entrá a Mis Expedientes y dejá visible la lista. Luego presioná ENTER acá...")

        rows = page.locator("table tbody tr")
        count = rows.count()

        data = []

        for i in range(count):
            row = rows.nth(i)
            cells = row.locator("td")
            cell_count = cells.count()

            if cell_count < 5:
                continue

            expediente = cells.nth(0).inner_text().strip()
            dependencia = cells.nth(1).inner_text().strip()
            caratula = cells.nth(2).inner_text().strip()
            situacion = cells.nth(3).inner_text().strip()
            ultima_act = cells.nth(4).inner_text().strip()

            data.append({
                "Número de expediente": expediente,
                "Juzgado": dependencia,
                "Carátula": caratula,
                "Situación": situacion,
                "Últ. Act. listado": ultima_act,
            })

        df = pd.DataFrame(data)
        df.to_excel("expedientes_pjn.xlsx", index=False)
        df.to_csv("expedientes_pjn.csv", index=False, encoding="utf-8-sig")

        print(f"Listo. Se exportaron {len(data)} expedientes.")
        print("Archivos generados: expedientes_pjn.xlsx y expedientes_pjn.csv")

        browser.close()

if __name__ == "__main__":
    main()
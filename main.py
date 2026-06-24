from playwright.sync_api import sync_playwright
import pandas as pd


def limpiar(texto: str) -> str:
    return " ".join(texto.replace("\n", " ").split())


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        print("\nPestañas abiertas:")
        for idx, page in enumerate(context.pages):
            print(f"{idx}: {page.url}")

        opcion = int(
            input("\nNúmero de pestaña con Lista de Expedientes Relacionados: ")
        )
        page = context.pages[opcion]
        page.bring_to_front()

        rows = page.locator("table tbody tr")
        count = rows.count()

        data = []

        for i in range(count):
            cells = rows.nth(i).locator("td")

            if cells.count() < 5:
                continue

            expediente = limpiar(cells.nth(0).inner_text())
            dependencia = limpiar(cells.nth(1).inner_text())
            caratula = limpiar(cells.nth(2).inner_text())
            situacion = limpiar(cells.nth(3).inner_text())
            ultima_act = limpiar(cells.nth(4).inner_text())

            if expediente in ["D", "N"]:
                continue

            if "Ver Causa" in situacion or "Ver Documento" in ultima_act:
                continue

            data.append(
                {
                    "Número de expediente": expediente,
                    "Juzgado": dependencia,
                    "Carátula": caratula,
                    "Situación": situacion,
                    "Últ. Act. listado": ultima_act,
                }
            )

        df = pd.DataFrame(data)
        df.to_excel("expedientes_pjn.xlsx", index=False)
        df.to_csv("expedientes_pjn.csv", index=False, encoding="utf-8-sig")

        print(f"\nListo. Se exportaron {len(data)} expedientes.")
        browser.close()


if __name__ == "__main__":
    main()

from io import BytesIO
from zipfile import ZipFile

import pytest

from mkvip.providers.global_indices import PublicIndexProvider


def test_lists_public_indices_by_country() -> None:
    indices = PublicIndexProvider(
        fetch_text=lambda _: "",
        fetch_json=lambda _: {},
    ).list_indices()

    assert [(index.code, index.country) for index in indices] == [
        ("DAX40", "Allemagne"),
        ("FTSE100", "Royaume-Uni"),
        ("IBEX35", "Espagne"),
        ("ATHEXCOMP", "Grèce"),
        ("FTSEMIB", "Italie"),
        ("SMI", "Suisse"),
        ("DOWJONES", "États-Unis"),
        ("SP500", "États-Unis"),
        ("NASDAQ100", "États-Unis"),
    ]


@pytest.mark.asyncio
async def test_parses_all_athex_composite_pages() -> None:
    overview = """
    <table><tr><th>Date Of Last Adjustement</th><td>2026.08.07</td></tr></table>
    """
    first_page = """
    <table><tbody>
      <tr>
        <td class="field--symbol">EEE</td>
        <td class="field--security mobile-hidden">COCA-COLA HBC AG (CR)</td>
      </tr>
    </tbody></table>
    <a href="?page=1">2</a>
    """
    second_page = """
    <table><tbody>
      <tr>
        <td class="field--symbol">TPEIR</td>
        <td class="field--security mobile-hidden">PIRAEUS BANK S.A. (CR)</td>
      </tr>
    </tbody></table>
    """

    def fetch_text(url: str) -> str:
        if url.endswith("/GD"):
            return overview
        if url.endswith("?page=1"):
            return second_page
        return first_page

    composition = await PublicIndexProvider(
        fetch_text=fetch_text,
        fetch_json=lambda _: {
            "data": [
                {"Symbol": "EEE", "ISIN": "CH0198251305"},
                {"Symbol": "TPEIR", "ISIN": "GRS014003032"},
            ]
        },
    ).get_composition("ATHEXCOMP")

    assert composition.name == "ATHEX Composite"
    assert composition.isin == "GRI99117A004"
    assert composition.as_of == "2026.08.07"
    assert [company.ticker for company in composition.constituents] == [
        "EEE.AT",
        "TPEIR.AT",
    ]
    assert composition.constituents[0].name == "COCA-COLA HBC AG"
    assert composition.constituents[0].isin == "CH0198251305"
    assert all(company.mic == "XATH" for company in composition.constituents)


@pytest.mark.asyncio
async def test_parses_blackrock_dax_holdings_and_ignores_cash() -> None:
    def point(value, formatted_value=None):
        return {"value": value, "formattedValue": formatted_value}

    payload = {
        "componentsByNameMap": {
            "holdings": {
                "containersByNameMap": {
                    "all": {
                        "dataPointsByNameMap": {
                            "asOfDate": point(20260803, "03/Aug/2026"),
                            "ticker": point(["SAP", "EUR"]),
                            "issueName": point(["SAP SE", "EUR CASH"]),
                            "assetClass": point(["Equity", "Cash"]),
                            "isin": point(["DE0007164600", "-"]),
                            "countryOfRisk": point(["Germany", "European Union"]),
                            "exchange": point(["Xetra", "-"]),
                            "marketCurrencyCode": point(["EUR", "EUR"]),
                        }
                    }
                }
            }
        }
    }
    provider = PublicIndexProvider(fetch_json=lambda _: payload)

    composition = await provider.get_composition("DAX40")

    assert composition.country == "Allemagne"
    assert composition.as_of == "03/Aug/2026"
    assert [company.ticker for company in composition.constituents] == ["SAP"]
    assert composition.constituents[0].isin == "DE0007164600"


@pytest.mark.asyncio
async def test_builds_ibex_35_official_snapshot() -> None:
    composition = await PublicIndexProvider().get_composition("IBEX35")

    assert composition.provider == "BME"
    assert composition.as_of == "Juin 2026"
    assert len(composition.constituents) == 35
    assert {company.ticker for company in composition.constituents} >= {
        "BBVA",
        "IBE",
        "SAN",
    }


@pytest.mark.asyncio
async def test_parses_ishares_smi_json() -> None:
    payload = {
        "aaData": [
            [
                "NOVN",
                "NOVARTIS AG",
                "Health Care",
                "Equity",
                {},
                {},
                {},
                {},
                "CH0012005267",
                {},
                "Switzerland",
                "SIX Swiss Exchange",
                "CHF",
            ],
            ["CHF", "CHF CASH", "Cash", "Cash", {}, {}, {}, {}, "-", {}, "-", "-", "CHF"],
        ]
    }
    provider = PublicIndexProvider(fetch_json=lambda _: payload)

    composition = await provider.get_composition("SMI")

    assert [company.ticker for company in composition.constituents] == ["NOVN"]
    assert composition.constituents[0].currency == "CHF"


def _state_street_workbook() -> bytes:
    rows = [
        ["Holdings:", "As of 04-Aug-2026"],
        [
            "Name",
            "Ticker",
            "Identifier",
            "SEDOL",
            "Weight",
            "Sector",
            "Shares Held",
            "Local Currency",
        ],
        ["MICROSOFT CORP", "MSFT", "594918104", "2588173", "5.4", "-", "10", "USD"],
        ["US DOLLAR", "-", "999USDZ92", "-", "0.1", "-", "100", "USD"],
    ]
    shared = [value for row in rows for value in row]
    position = 0
    xml_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for _value in row:
            cells.append(f'<c t="s"><v>{position}</v></c>')
            position += 1
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    shared_xml = (
        f'<sst xmlns="{namespace}">'
        + "".join(f"<si><t>{value}</t></si>" for value in shared)
        + "</sst>"
    )
    sheet_xml = (
        f'<worksheet xmlns="{namespace}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


@pytest.mark.asyncio
async def test_parses_state_street_dow_workbook() -> None:
    provider = PublicIndexProvider(fetch_bytes=lambda _: _state_street_workbook())

    composition = await provider.get_composition("DOWJONES")

    assert composition.as_of == "04-Aug-2026"
    assert [company.ticker for company in composition.constituents] == ["MSFT"]
    assert composition.constituents[0].mic == "XNAS"


@pytest.mark.asyncio
async def test_parses_ishares_sp500_holdings() -> None:
    header = [
        "Ticker",
        "Name",
        "Sector",
        "Asset Class",
        "Market Value",
        "Weight (%)",
        "Notional Value",
        "Quantity",
        "Price",
        "Location",
        "Exchange",
        "Currency",
        "FX Rate",
        "Market Currency",
        "Accrual Date",
    ]
    payload = "\n".join(
        [
            "iShares Core S&P 500 ETF",
            'Fund Holdings as of,"Aug 03, 2026"',
            ",".join(header),
            '"AAPL","APPLE INC","Technology","Equity","1","1","1","1","1",'
            '"United States","NASDAQ","USD","1","USD","-"',
            '"BRKB","BERKSHIRE HATHAWAY INC CLASS B","Financials","Equity","1",'
            '"1","1","1","1","United States","NYSE","USD","1","USD","-"',
            '"USD","USD CASH","Cash","Cash","1","1","1","1","1",'
            '"United States","-","USD","1","USD","-"',
        ]
    )
    provider = PublicIndexProvider(fetch_text=lambda _: payload)

    composition = await provider.get_composition("SP500")

    assert composition.as_of == "Aug 03, 2026"
    assert [company.ticker for company in composition.constituents] == [
        "AAPL",
        "BRK-B",
    ]
    assert composition.constituents[0].mic == "XNAS"
    assert composition.constituents[1].currency == "USD"


@pytest.mark.asyncio
async def test_parses_nasdaq_100_api() -> None:
    payload = {
        "data": {
            "date": "Aug 4, 2026 3:53 PM",
            "data": {
                "rows": [
                    {
                        "symbol": "MSFT",
                        "companyName": "Microsoft Corporation Common Stock",
                    },
                    {
                        "symbol": "AAPL",
                        "companyName": "Apple Inc. Common Stock",
                    },
                ]
            },
        }
    }
    provider = PublicIndexProvider(fetch_json=lambda _: payload)

    composition = await provider.get_composition("NASDAQ100")

    assert composition.as_of == "Aug 4, 2026 3:53 PM"
    assert [company.ticker for company in composition.constituents] == [
        "MSFT",
        "AAPL",
    ]
    assert all(company.mic == "XNAS" for company in composition.constituents)

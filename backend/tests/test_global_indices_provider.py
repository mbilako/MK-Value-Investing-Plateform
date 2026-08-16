from io import BytesIO
from zipfile import ZipFile

import pytest

from mkvip.providers.global_indices import PublicIndexProvider
from mkvip.providers.index_catalog import IndexCatalogProvider


def test_catalog_exposes_general_and_sector_indices_for_every_european_country() -> None:
    indices = [
        index
        for index in IndexCatalogProvider().list_indices()
        if index.region == "Europe" and index.country != "Europe"
    ]
    counts = {
        country: len([index for index in indices if index.country == country])
        for country in {index.country for index in indices}
    }

    assert counts == {
        "Allemagne": 13,
        "Belgique": 14,
        "Espagne": 6,
        "France": 14,
        "Grèce": 12,
        "Irlande": 12,
        "Italie": 13,
        "Pays-Bas": 14,
        "Portugal": 11,
        "Royaume-Uni": 14,
        "Suisse": 13,
    }
    assert all(
        any(index.country == country and index.kind == "sector" for index in indices)
        for country in counts
    )


def test_lists_public_indices_by_country() -> None:
    indices = PublicIndexProvider(
        fetch_text=lambda _: "",
        fetch_json=lambda _: {},
    ).list_indices()
    indices = [index for index in indices if index.kind == "broad"]

    assert [(index.code, index.country) for index in indices] == [
        ("DAX40", "Allemagne"),
        ("MDAX", "Allemagne"),
        ("TECDAX", "Allemagne"),
        ("FTSE100", "Royaume-Uni"),
        ("FTSE250", "Royaume-Uni"),
        ("MSCIUKSC", "Royaume-Uni"),
        ("IBEX35", "Espagne"),
        ("IBEXMEDIUM", "Espagne"),
        ("IBEXSMALL", "Espagne"),
        ("ATHEXCOMP", "Grèce"),
        ("ATHEXLARGE", "Grèce"),
        ("ATHEXMID", "Grèce"),
        ("FTSEMIB", "Italie"),
        ("FTSEITMID", "Italie"),
        ("FTSEITSMALL", "Italie"),
        ("SMI", "Suisse"),
        ("SMIM", "Suisse"),
        ("SPI", "Suisse"),
        ("DOWJONES", "États-Unis"),
        ("SP500", "États-Unis"),
        ("NASDAQ100", "États-Unis"),
        ("CSI300", "Chine"),
    ]


def test_lists_sector_indices_in_each_geographic_region() -> None:
    indices = [index for index in PublicIndexProvider().list_indices() if index.kind == "sector"]

    assert {
        region: len([index for index in indices if index.region == region])
        for region in {index.region for index in indices}
    } == {"Europe": 59, "États-Unis": 11, "Chine": 11}
    assert {index.sector for index in indices if index.region == "Europe"} == {
        "Communication Services",
        "Consumer Discretionary",
        "Consumer Staples",
        "Energy",
        "Financials",
        "Health Care",
        "Industrials",
        "Information Technology",
        "Materials",
        "Real Estate",
        "Utilities",
    }
    assert {index.sector for index in indices if index.region == "États-Unis"} == {
        "Communication Services",
        "Consumer Discretionary",
        "Consumer Staples",
        "Energy",
        "Financials",
        "Health Care",
        "Industrials",
        "Information Technology",
        "Materials",
        "Real Estate",
        "Utilities",
    }
    assert {index.sector for index in indices if index.region == "Chine"} == {
        "Communication Services",
        "Consumer Discretionary",
        "Consumer Staples",
        "Energy",
        "Financials",
        "Health Care",
        "Industrials",
        "Information Technology",
        "Materials",
        "Real Estate",
        "Utilities",
    }
    assert all(
        index.name.startswith("S&P 500 ") for index in indices if index.region == "États-Unis"
    )
    assert all("Russell" not in index.name for index in indices)


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
async def test_preserves_european_sector_metadata_and_component_market() -> None:
    def point(value, formatted_value=None):
        return {"value": value, "formattedValue": formatted_value}

    payload = {
        "componentsByNameMap": {
            "holdings": {
                "containersByNameMap": {
                    "all": {
                        "dataPointsByNameMap": {
                            "asOfDate": point(20260813, "13/Aug/2026"),
                            "ticker": point(["SAN", "NOVO B"]),
                            "issueName": point(["BANCO SANTANDER SA", "NOVO NORDISK CLASS B"]),
                            "assetClass": point(["Equity", "Equity"]),
                            "isin": point(["ES0113900J37", "DK0062498333"]),
                            "countryOfRisk": point(["Spain", "Denmark"]),
                            "exchange": point(["Bolsa De Madrid", "Nasdaq Omx Nordic"]),
                            "marketCurrencyCode": point(["EUR", "DKK"]),
                        }
                    }
                }
            }
        }
    }
    composition = await PublicIndexProvider(fetch_json=lambda _: payload).get_composition(
        "EUROPEBANKS"
    )

    assert composition.kind == "sector"
    assert composition.sector == "Financials"
    assert [company.mic for company in composition.constituents] == ["XMAD", "XCSE"]


@pytest.mark.asyncio
async def test_filters_a_dax_national_sector_from_blackrock_holdings() -> None:
    def point(value, formatted_value=None):
        return {"value": value, "formattedValue": formatted_value}

    payload = {
        "componentsByNameMap": {
            "holdings": {
                "containersByNameMap": {
                    "all": {
                        "dataPointsByNameMap": {
                            "asOfDate": point(20260815, "15/Aug/2026"),
                            "ticker": point(["SAP", "ALV"]),
                            "issueName": point(["SAP SE", "ALLIANZ SE"]),
                            "assetClass": point(["Equity", "Equity"]),
                            "isin": point(["DE0007164600", "DE0008404005"]),
                            "countryOfRisk": point(["Germany", "Germany"]),
                            "exchange": point(["Xetra", "Xetra"]),
                            "marketCurrencyCode": point(["EUR", "EUR"]),
                            "sectorName": point(["Information Technology", "Financials"]),
                        }
                    }
                }
            }
        }
    }

    composition = await PublicIndexProvider(fetch_json=lambda _: payload).get_composition("DETECH")

    assert composition.country == "Allemagne"
    assert composition.kind == "sector"
    assert composition.sector == "Information Technology"
    assert [company.ticker for company in composition.constituents] == ["SAP"]


@pytest.mark.asyncio
async def test_filters_a_swiss_national_sector_from_ishares_json() -> None:
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
            [
                "UBSG",
                "UBS GROUP AG",
                "Financials",
                "Equity",
                {},
                {},
                {},
                {},
                "CH0244767585",
                {},
                "Switzerland",
                "SIX Swiss Exchange",
                "CHF",
            ],
        ]
    }

    composition = await PublicIndexProvider(fetch_json=lambda _: payload).get_composition(
        "CHHEALTH"
    )

    assert composition.country == "Suisse"
    assert composition.kind == "sector"
    assert [company.ticker for company in composition.constituents] == ["NOVN"]


@pytest.mark.asyncio
async def test_parses_us_sector_holdings() -> None:
    payload = "\n".join(
        [
            "iShares U.S. Healthcare ETF",
            'Fund Holdings as of,"Aug 13, 2026"',
            (
                "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),"
                "Notional Value,Quantity,Price,Location,Exchange,Currency,"
                "FX Rate,Market Currency,Accrual Date"
            ),
            (
                '"LLY","ELI LILLY","Health Care","Equity","1","1","1",'
                '"1","1","United States","NYSE","USD","1","USD","-"'
            ),
            (
                '"AAPL","APPLE INC","Information Technology","Equity","1","1","1",'
                '"1","1","United States","NASDAQ","USD","1","USD","-"'
            ),
        ]
    )
    composition = await PublicIndexProvider(fetch_text=lambda _: payload).get_composition(
        "USHEALTH"
    )

    assert composition.kind == "sector"
    assert composition.sector == "Health Care"
    assert [company.ticker for company in composition.constituents] == ["LLY"]


@pytest.mark.asyncio
async def test_parses_csi_300_and_filters_its_gics_sectors() -> None:
    payload = "\n".join(
        [
            'Fund Holdings as of,"14-Aug-2026"',
            (
                "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),"
                "Notional Value,Shares,Price,Location,Exchange,Currency,"
                "FX Rate,Market Currency"
            ),
            (
                '"300308","ZHONGJI INNOLIGHT A","Information Technology",'
                '"Equity","1","1","1","1","1","China",'
                '"Shenzhen Stock Exchange","CNY","1","CNY"'
            ),
            (
                '"600519","KWEICHOW MOUTAI A","Consumer Staples","Equity",'
                '"1","1","1","1","1","China","Shanghai Stock Exchange",'
                '"CNY","1","CNY"'
            ),
        ]
    )
    provider = PublicIndexProvider(fetch_text=lambda _: payload)

    broad = await provider.get_composition("CSI300")
    technology = await provider.get_composition("CNTECH")

    assert broad.as_of == "14-Aug-2026"
    assert [company.ticker for company in broad.constituents] == ["300308", "600519"]
    assert [company.mic for company in broad.constituents] == ["XSHE", "XSHG"]
    assert [company.currency for company in broad.constituents] == ["CNY", "CNY"]
    assert [company.ticker for company in technology.constituents] == ["300308"]
    assert technology.kind == "sector"
    assert technology.sector == "Information Technology"


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
async def test_builds_ibex_medium_and_small_official_snapshots() -> None:
    provider = PublicIndexProvider()

    medium = await provider.get_composition("IBEXMEDIUM")
    small = await provider.get_composition("IBEXSMALL")

    assert medium.as_of == "Juin 2026"
    assert len(medium.constituents) == 20
    assert {company.ticker for company in medium.constituents} >= {"AMP", "CIRSA", "OHLA"}
    assert len(small.constituents) >= 29
    assert {company.ticker for company in small.constituents} >= {"GEST", "TSK", "TUB"}


@pytest.mark.asyncio
async def test_parses_all_borsa_italiana_pages() -> None:
    first_page = """
    <a href="/borsa/azioni/scheda/IT0001207098-MTAA.html?lang=en">Acea</a>
    <a href="?page=2">2</a>
    """
    second_page = """
    <a href="/borsa/azioni/scheda/IT0000062072-MTAA.html?lang=en">
      Generali
    </a>
    """

    def fetch_text(url: str) -> str:
        return second_page if "page=2" in url else first_page

    composition = await PublicIndexProvider(fetch_text=fetch_text).get_composition("FTSEITMID")

    assert [company.name for company in composition.constituents] == ["Acea", "Generali"]
    assert [company.isin for company in composition.constituents] == [
        "IT0001207098",
        "IT0000062072",
    ]
    assert all(company.mic == "XMIL" for company in composition.constituents)


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

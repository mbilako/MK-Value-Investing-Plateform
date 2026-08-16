from mkvip.providers.euronext import EuronextIndex, EuronextIndexProvider, _parse_composition


def test_supported_indices_include_major_euronext_markets() -> None:
    indices = EuronextIndexProvider(fetch_json=lambda _: {}).list_indices()
    names = [index.name for index in indices]
    assert {
        "CAC 40",
        "AEX",
        "BEL 20",
        "PSI",
        "ISEQ 20",
        "CAC Financials",
        "AEX Technology",
        "BEL Health Care",
        "PSI Industrials",
        "ISEQ Financial",
    } <= set(names)
    assert len([index for index in indices if index.kind == "sector"]) == 52
    assert {
        country: len([index for index in indices if index.country == country])
        for country in {index.country for index in indices}
    } == {
        "France": 14,
        "Pays-Bas": 14,
        "Belgique": 14,
        "Portugal": 11,
        "Irlande": 12,
    }
    sectors = {index.code: index.sector for index in indices if index.kind == "sector"}
    assert sectors["PSIIND"] == "Industrials"
    assert sectors["ISEQFIN"] == "Financials"
    assert sectors["CACHEALTH"] == "Health Care"


def test_parses_euronext_composition_rows() -> None:
    html = """
    <h6>31/07/2026</h6>
    <table><tbody><tr>
      <td>1</td>
      <td><a href="/fr/product/equities/FR0000120073-XPAR">AIR LIQUIDE</a></td>
      <td>Euronext Paris</td><td>France</td>
    </tr></tbody></table>
    """
    result = _parse_composition(
        EuronextIndex("CAC40", "CAC 40", "FR0003500008"),
        "https://live.euronext.com/example",
        html,
    )

    assert result.as_of == "31/07/2026"
    assert result.constituents[0].model_dump() == {
        "name": "AIR LIQUIDE",
        "isin": "FR0000120073",
        "ticker": None,
        "mic": "XPAR",
        "trading_location": "Euronext Paris",
        "country": "France",
        "currency": "EUR",
    }

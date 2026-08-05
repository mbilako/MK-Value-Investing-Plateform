from mkvip.providers.euronext import EuronextIndex, EuronextIndexProvider, _parse_composition


def test_supported_indices_include_major_euronext_markets() -> None:
    indices = EuronextIndexProvider(fetch_json=lambda _: {}).list_indices()
    names = [index.name for index in indices]
    assert names == [
        "CAC 40",
        "CAC Next 20",
        "SBF 120",
        "AEX",
        "BEL 20",
        "PSI",
        "ISEQ 20",
    ]
    assert [(index.name, index.country) for index in indices[-4:]] == [
        ("AEX", "Pays-Bas"),
        ("BEL 20", "Belgique"),
        ("PSI", "Portugal"),
        ("ISEQ 20", "Irlande"),
    ]


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

from mkvip.providers.euronext import EuronextIndex, EuronextIndexProvider, _parse_composition


def test_supported_indices_include_cac_next_20() -> None:
    names = [index.name for index in EuronextIndexProvider(fetch_json=lambda _: {}).list_indices()]
    assert names == ["CAC 40", "CAC Next 20", "SBF 120"]


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
        "mic": "XPAR",
        "trading_location": "Euronext Paris",
        "country": "France",
    }

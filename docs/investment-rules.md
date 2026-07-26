# Règles d’investissement initiales

Le premier catalogue reprend les seuils explicites du classeur
`règles d'investissement.xlsx`. Les règles restent isolées du transport HTTP
et de la base de données afin de pouvoir être testées et versionnées.

| Clé | Critère | Favorable | Défavorable |
|---|---|---:|---:|
| `ebitda_margin` | Marge EBITDA | > 40 % | < 20 % |
| `depreciation_to_ebit` | Amortissements / EBIT | < 10 % | seuil conservateur provisoire ≥ 20 % |
| `interest_to_ebit` | Charges d’intérêts / EBIT | < 15 % | seuil conservateur provisoire ≥ 30 % |
| `capex_to_net_income` | Investissements / résultat net | < 25 % | > 50 % |
| `pe_ratio` | PER | < 20 | > 40 |
| `net_margin` | Marge nette | > 20 % | < 10 % |
| `financial_leverage` | Effet de levier | < 0,8 | seuil conservateur provisoire ≥ 1,5 |
| `current_ratio` | Actif circulant / passif exigible | > 2 | seuil conservateur provisoire < 1 |
| `market_cap_to_assets` | Capitalisation / actif total | < 1,5 | seuil conservateur provisoire ≥ 2,5 |
| `net_debt_to_ebitda` | Dette nette / EBITDA | < 2,5 | > 5 hors LBO |

Les zones comprises entre les seuils favorables et défavorables reçoivent le
statut `review`. Les seuils défavorables non explicitement présents dans le
classeur sont signalés comme provisoires et devront être validés par le
Product Owner avant le calcul du MK Score.

## Formules du snapshot financier

| Clé | Formule |
|---|---|
| `ebitda_margin` | EBITDA / chiffre d’affaires |
| `depreciation_to_ebit` | dotations aux amortissements / EBIT |
| `interest_to_ebit` | charges d’intérêts / EBIT |
| `capex_to_net_income` | investissements / résultat net |
| `pe_ratio` | capitalisation boursière / résultat net |
| `net_margin` | résultat net / chiffre d’affaires |
| `financial_leverage` | dette financière / capitaux propres |
| `current_ratio` | actif circulant / passif exigible |
| `market_cap_to_assets` | capitalisation boursière / total actif |
| `net_debt_to_ebitda` | (dette financière − trésorerie) / EBITDA |

Le MK Score est calculé ainsi :

```text
nombre de règles favorables / nombre total de règles × 100
```

Une règle au statut `review` ou `fail` ne contribue pas au score. Ce score est
un outil de présélection explicable, pas une recommandation d’investissement.

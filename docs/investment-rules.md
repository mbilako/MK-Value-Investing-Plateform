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

Le calcul est réalisé séparément pour chaque exercice importé. L’interface
affiche jusqu’à dix MK Scores annuels afin de distinguer une qualité durable
d’un résultat ponctuel ; aucune moyenne pluriannuelle arbitraire n’est ajoutée.

Une règle au statut `review` ou `fail` ne contribue pas au score. Ce score est
un outil de présélection explicable, pas une recommandation d'investissement.

Le calcul standard s'applique aux sociétés non financières. Pour une banque ou
un assureur, le MK Score est affiché comme **non applicable** tant qu'un
catalogue sectoriel distinct (solvabilité, qualité des actifs, coût du risque,
ratio combiné, etc.) n'a pas été validé. Un dénominateur nul ou négatif sur une
règle standard est classé défavorable et n'améliore jamais le score.

## Scores spécialisés

Le score de qualité agrège les règles de marge EBITDA, amortissements / EBIT,
investissements / résultat net et marge nette. Le score de sécurité agrège les
règles de charges d’intérêts / EBIT, levier financier, ratio courant et dette
nette / EBITDA. Chaque score suit la même convention que le MK Score :
pourcentage de règles favorables dans son groupe.

Le Free Cash Flow, sa marge, le ROE, le ROIC, la couverture des intérêts et la
dette nette restent des indicateurs informatifs en v0.4. Aucun seuil nouveau
n’est inventé pour ces indicateurs.

## Scoring global v0.6

Le MK Global Score est la moyenne pondérée de quatre composantes de même poids :

| Composante | Poids | Origine |
|---|---:|---|
| MK Quality Score | 25 % | règles de rentabilité du Financial Engine |
| MK Safety Score | 25 % | règles de solidité du Financial Engine |
| MK Value Score | 25 % | écart entre estimation centrale et capitalisation |
| MK Moat Score | 25 % | proxy fondé sur quatre signaux quantitatifs |

```text
MK Value Score = borne(50 + écart de marché × 200, 0, 100)
MK Moat Score = signaux favorables / 4 × 100
MK Global Score = somme(score de composante × 25 %)
```

Le score de valeur vaut 50 à la juste valeur, 100 à partir de 25 % de décote et
0 à partir de 25 % de surcote. Le proxy de moat compte une marge EBITDA
favorable, une marge nette favorable, un ROIC supérieur au WACC et un Free
Cash Flow positif. Il ne remplace pas l’analyse qualitative de la marque, des
coûts de changement, des effets de réseau ou de la gouvernance.

Le signal est « Profil favorable » à partir de 75/100 si aucune composante
n’est inférieure à 50, « À approfondir » à partir de 55/100, et « Prudence »
en dessous. Il priorise la recherche et ne constitue pas une recommandation.

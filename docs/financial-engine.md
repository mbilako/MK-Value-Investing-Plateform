# Financial Engine v0.4

Le Financial Engine transforme chaque snapshot annuel normalisé en indicateurs
et scores explicables. Il ne dépend d’aucun fournisseur de données.

## Indicateurs

| Indicateur | Formule |
|---|---|
| Free Cash Flow | flux de trésorerie opérationnel − investissements |
| Marge de Free Cash Flow | Free Cash Flow / chiffre d’affaires |
| ROE | résultat net / capitaux propres |
| ROIC avant impôt | EBIT / (capitaux propres + dette financière − trésorerie) |
| Couverture des intérêts | EBIT / charges d’intérêts |
| Dette nette | dette financière − trésorerie |

Le ROIC est un proxy avant impôt : le contrat v0.4 ne collecte pas encore le
taux d’imposition effectif nécessaire au NOPAT. Il ne doit donc pas être
comparé sans précaution à un ROIC après impôt publié par un émetteur.

La couverture des intérêts n’est pas calculée lorsque les charges d’intérêts
sont nulles ou négatives. Les autres ratios dépendant d’un dénominateur nul
sont également restitués comme indisponibles.

## Scores

- MK Score : ensemble des dix règles historiques.
- Qualité : marge EBITDA, amortissements / EBIT, investissements / résultat
  net et marge nette.
- Sécurité : charges d’intérêts / EBIT, levier financier, ratio courant et
  dette nette / EBITDA.

Chaque score correspond au nombre de règles favorables divisé par le nombre de
règles de son groupe, multiplié par 100.

## Tendances

À partir de deux exercices comparables, le moteur calcule le taux de croissance
annualisé composé du chiffre d’affaires, du résultat net, du Free Cash Flow et
des capitaux propres :

```text
CAGR = (valeur finale / valeur initiale)^(1 / nombre d’années) − 1
```

Une tendance est indisponible si l’historique comporte moins de deux exercices,
si une valeur de départ ou d’arrivée n’est pas strictement positive, ou si les
années ne forment pas un intervalle positif.

## Traçabilité et limites

La source et l’exercice restent attachés à chaque snapshot. Les données
publiques doivent être rapprochées des états financiers audités. Les
indicateurs et scores servent à structurer l’analyse ; ils ne constituent pas
une recommandation d’achat ou de vente.

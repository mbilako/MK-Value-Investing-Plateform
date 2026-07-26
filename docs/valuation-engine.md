# Valuation Engine v0.5

Le Valuation Engine transforme le dernier snapshot financier normalisé en
scénario de valorisation explicable. Toutes les valeurs calculées représentent
les capitaux propres totaux, en millions dans la devise du snapshot. Ce moteur
est un outil de recherche : il ne constitue pas une recommandation
d’investissement.

## Contrat du scénario

Chaque scénario conserve :

- le snapshot et l’exercice utilisés ;
- la capitalisation observée, si elle est fournie ;
- les taux de croissance, d’actualisation, d’impôt et de marge de sécurité ;
- l’horizon explicite, le multiple cible et le rendement obligataire de
  référence ;
- les cinq résultats, leur formule et leur note méthodologique.

Le coût des capitaux propres doit être strictement supérieur à la croissance
terminale. Les taux sont saisis comme pourcentages dans l’interface et transmis
comme décimales à l’API.

## Méthodes

### DCF des flux disponibles

Le flux de départ est le Free Cash Flow approché :

```text
FCF = flux de trésorerie opérationnel - dépenses d’investissement
```

Il est projeté sur l’horizon explicite avec le taux de croissance, actualisé au
coût des capitaux propres, puis complété par une valeur terminale de Gordon.
Cette version utilise un flux disponible aux actionnaires approché ; elle ne
remplace pas une reconstruction détaillée du besoin en fonds de roulement.

### Buffett Owner Earnings

Le flux de départ suit l’idée publiée par Warren Buffett :

```text
Owner Earnings = résultat net + amortissements - dépenses d’investissement
```

La projection et la valeur terminale suivent la même mécanique que le DCF.
Faute de ventilation normalisée, les dépenses d’investissement totales servent
de proxy aux investissements nécessaires et les variations de besoin en fonds
de roulement ne sont pas isolées.

### Earnings Power Value

L’EPV capitalise le résultat opérationnel après impôt sans croissance :

```text
EPV = EBIT × (1 - taux d’impôt) / WACC - dette + trésorerie
```

Elle représente une puissance bénéficiaire stabilisée. Les ajustements
comptables détaillés d’une analyse EPV complète ne sont pas automatisés en
v0.5.

### Formule de Graham

La formule historique est appliquée au résultat net total :

```text
Valeur = résultat net × (8,5 + 2 × croissance en points) × (4,4 / rendement AAA en %)
```

Le rendement obligataire est une hypothèse explicite. Cette formule est un
repère historique sensible à la croissance et au taux choisis, pas une valeur
intrinsèque autonome.

### Multiple de résultat

La méthode relative applique un multiple cible :

```text
Valeur = résultat net × P/E cible
```

Le multiple doit être justifié par des comparables cohérents en secteur,
qualité, croissance et structure de capital.

## Synthèse

L’estimation centrale est la médiane des valeurs strictement positives et
calculables. Cette convention limite l’influence d’une méthode extrême sans
masquer le détail. La valeur avec marge de sécurité est :

```text
Valeur de sécurité = estimation centrale × (1 - marge de sécurité)
```

Lorsque la capitalisation est disponible, l’écart affiché est :

```text
Écart = estimation centrale / capitalisation - 1
```

Une méthode dont le flux de départ n’est pas positif reste visible mais est
exclue de la médiane.

## Références méthodologiques

- [Berkshire Hathaway, lettre 1986 — définition des Owner Earnings](https://www.berkshirehathaway.com/letters/1986.html)
- [NYU Stern, Aswath Damodaran — fondements de la valorisation](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/lectures/val.html)
- [NYU Stern — croissance stable et valeur terminale](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/littlebook/terminalvalue.htm)
- [NYU Stern — introduction à la valorisation relative](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/relintro.pdf)
- [Columbia Business School — principes de l’EPV](https://business.columbia.edu/sites/default/files-efs/imce-uploads/DG_Audun%20Nordtveit.pdf)

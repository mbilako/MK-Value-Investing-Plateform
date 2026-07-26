# Scoring Engine v0.6

Le Scoring Engine synthétise un snapshot financier et une valorisation du même
exercice en une priorité de recherche explicable. Il ne constitue ni une
recommandation d’achat, ni une mesure exhaustive de la qualité d’une entreprise.

## Contrat du calcul

Chaque analyse conserve :

- l’entreprise, le snapshot financier et la valorisation utilisés ;
- quatre composantes notées de 0 à 100 ;
- le poids, la contribution, la formule et la note de chaque composante ;
- quatre explications en langage clair ;
- le MK Global Score et son signal de présélection.

Le calcul exige une valorisation avec un écart de marché mesurable. Un nouveau
calcul crée un nouvel enregistrement afin de garder l’historique.

## Composantes

Les quatre composantes ont un poids de 25 %.

### MK Quality Score

Le score provient du Financial Engine. Il mesure la part de règles favorables
parmi la marge EBITDA, les amortissements rapportés à l’EBIT, les dépenses
d’investissement rapportées au résultat net et la marge nette.

### MK Safety Score

Le score provient également du Financial Engine. Il mesure la part de règles
favorables parmi la charge d’intérêts, le levier financier, le ratio courant et
la dette nette rapportée à l’EBITDA.

### MK Value Score

```text
écart de marché = estimation centrale / capitalisation - 1
MK Value Score = borne(50 + écart de marché × 200, 0, 100)
```

Une valeur égale à la capitalisation donne 50/100. Une décote de 25 % ou plus
donne 100/100 ; une surcote de 25 % ou plus donne 0/100. La borne évite qu’une
valorisation extrême domine la synthèse.

### MK Moat Score

Cette composante est un proxy quantitatif. Elle compte quatre signaux :

1. marge EBITDA au statut favorable ;
2. marge nette au statut favorable ;
3. ROIC supérieur au WACC du scénario ;
4. Free Cash Flow positif.

```text
MK Moat Score = nombre de signaux favorables / 4 × 100
```

La durée des rendements excédentaires est liée aux avantages compétitifs, mais
ces quatre signaux ne prouvent pas l’existence d’un moat. La marque, les coûts
de changement, les effets de réseau, la structure sectorielle, la gouvernance
et la durabilité des rendements doivent être étudiés séparément.

## Synthèse et signaux

```text
MK Global Score =
  Quality × 25 % +
  Safety × 25 % +
  Value × 25 % +
  Moat × 25 %
```

- `Profil favorable` : score global d’au moins 75 et aucune composante sous 50 ;
- `À approfondir` : score global d’au moins 55 ;
- `Prudence` : score global inférieur à 55.

Le garde-fou du premier signal empêche qu’une forte décote compense entièrement
une faiblesse marquée de qualité, de sécurité ou de moat.

## Limites

- La qualité et la sécurité restent dépendantes des seuils du catalogue métier.
- Le score de valeur hérite de toutes les hypothèses du scénario retenu.
- Le moat est un proxy instantané et quantitatif, pas une analyse concurrentielle.
- Les pondérations égales sont une convention v0.6 à valider par l’usage.
- Un score élevé ne remplace pas la lecture des comptes audités ni l’analyse
  qualitative de l’entreprise.

## Références méthodologiques

- [NYU Stern, Aswath Damodaran — définitions et relations de valorisation](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/definitions.html)
- [NYU Stern — Investment Valuation, support actualisé 2025](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/valpacket3spr25.pdf)
- [CFA Institute — Quality Investing](https://rpc.cfainstitute.org/research/financial-analysts-journal/2019/0015198x-2019-1567194)
- [CFA Institute — Quality Control](https://rpc.cfainstitute.org/research/cfa-magazine/2014/quality-control)

# Dashboard v0.7

Le dashboard transforme les derniers résultats déjà calculés en vue
comparative. Il aide à choisir quel dossier approfondir ; il ne produit ni
recommandation d’achat ni portefeuille détenu.

## Contrat API

`GET /api/v1/dashboard` renvoie trois ensembles :

- `summary` : nombre d’entreprises prêtes, scorées et réparties par signal ;
- `distribution` : libellé et compteur des quatre états de recherche ;
- `companies` : dernière lecture comparable de chaque entreprise.

Une ligne d’entreprise contient son identité, son statut, le dernier score
global, le signal, l’exercice, l’écart entre valeur centrale et
capitalisation, la composante la plus faible et la date du scoring.

## Règles d’agrégation

1. Le scoring le plus récent est retenu pour chaque entreprise.
2. L’écart de valeur vient de la valorisation référencée par ce scoring.
3. La composante ayant le score le plus faible devient le point à approfondir.
4. Les dossiers scorés sont classés par score global décroissant.
5. Les dossiers non scorés restent visibles après eux, par nom.
6. Les compteurs utilisent toujours les mêmes quatre états :
   `favorable`, `watch`, `caution` et `unscored`.

## Interprétation

- **Profil favorable** : dossier prioritaire pour la recherche selon les
  seuils actuels.
- **À approfondir** : résultat intermédiaire qui demande des vérifications.
- **Prudence** : score global ou composante faible appelant une attention
  particulière.
- **À scorer** : analyse comparative encore incomplète.

Le « portefeuille de recherche » n’est pas un portefeuille de titres détenus.
MK-VIP n’invente donc ni quantité, ni allocation, ni prix de revient, ni
performance. Toute décision reste fondée sur les sources auditées, les
hypothèses de valorisation et le détail explicable du scoring.

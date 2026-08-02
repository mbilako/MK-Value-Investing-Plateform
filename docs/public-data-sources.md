# Sources de données publiques

MK-VIP assemble uniquement des sources gratuites. Un import automatique
retient un exercice annuel complet auprès d’un seul fournisseur comptable ; il
ne mélange pas ligne par ligne des exercices ou des normes différentes.

## Ordre de repli financier

1. **Yahoo Finance** fournit le profil de marché et, lorsqu’ils sont complets,
   les trois états financiers annuels.
2. **SEC EDGAR** fournit les faits XBRL US-GAAP des formulaires annuels 10-K,
   20-F et 40-F. Le profil et la capitalisation de marché restent obtenus via
   Yahoo Finance et cette provenance combinée est explicitement enregistrée.
3. **ESEF européen** utilise les dépôts XBRL publics de
   [filings.xbrl.org](https://filings.xbrl.org/docs/api). L’ISIN est rapproché
   du LEI via l’API gratuite de [GLEIF](https://www.gleif.org/en/lei-data/gleif-api/).
   La capitalisation de marché reste issue de Yahoo Finance.

Si aucun fournisseur ne livre un compte de résultat, un bilan et un tableau de
flux complets pour le même exercice, l’import est refusé avec le détail des
sources essayées. L’utilisateur peut alors compléter les identifiants de
l’entreprise ou utiliser le formulaire manuel avec le rapport annuel audité.

## Référentiels d’entreprises et d’indices

Les compositions du **CAC 40**, du **CAC Next 20** et du **SBF 120** sont lues
dynamiquement auprès d’Euronext puis mises en cache pendant six heures. Chaque
composante inclut son nom, son ISIN, son marché MIC, sa place de cotation et son
pays. Le ticker Yahoo n’est résolu qu’au moment où l’utilisateur sélectionne
l’entreprise, ce qui évite toute saisie manuelle.

L’ajout multiple est idempotent : une entreprise déjà connue par son ISIN ou
son ticker n’est pas recréée, et ses appartenances aux indices sont fusionnées.

## Identifiants et traçabilité

Chaque entreprise peut conserver :

- l’**ISIN** pour le titre coté et le rapprochement avec les référentiels ;
- le **CIK** pour la SEC ;
- le **LEI** pour les dépôts réglementaires européens ;
- les symboles propres à chaque fournisseur ;
- la liste des indices auxquels elle appartient.

Chaque snapshot financier conserve le fournisseur effectivement utilisé, le
symbole ou identifiant interrogé et l’exercice. Le User-Agent SEC doit être
configuré avec un contact exploitable via `MKVIP_SEC_USER_AGENT`, conformément
aux règles d’accès équitable d’EDGAR.

## Limites

- Les sources gratuites peuvent être indisponibles, incomplètes, retardées ou
  modifier leurs interfaces et leurs limites d’usage.
- ESEF couvre les dépôts publiés et indexés ; certaines sociétés ou certains
  exercices peuvent être absents.
- La composition d’un indice évolue. MK-VIP affiche la date communiquée par
  Euronext et ne constitue pas un service de redistribution de données de
  marché.
- Les données importées restent une base de recherche et doivent être
  rapprochées du rapport annuel officiel avant toute décision.

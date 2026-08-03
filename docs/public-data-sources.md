# Sources de données publiques

MK-VIP assemble uniquement des sources gratuites. Un import automatique charge
jusqu’aux dix derniers exercices structurés disponibles. Chaque exercice est
retenu intégralement auprès d’un seul fournisseur comptable : aucune ligne d’un
même exercice n’est mélangée entre plusieurs normes ou plusieurs sources.

## Ordre de repli financier

1. **Yahoo Finance** fournit le profil de marché et, lorsqu’ils sont complets,
   les trois états financiers annuels.
2. **SEC EDGAR** fournit les faits XBRL US-GAAP des formulaires annuels 10-K,
   20-F et 40-F. Le profil et la capitalisation de marché restent obtenus via
   Yahoo Finance et cette provenance combinée est explicitement enregistrée.
   Un ticker portant un suffixe de place étrangère, par exemple `.PA`, n'est
   jamais tronqué pour chercher un homonyme américain. Un CIK explicite est
   exigé pour rapprocher une cotation non américaine d'EDGAR.
3. **ESEF européen** utilise les dépôts XBRL publics de
   [filings.xbrl.org](https://filings.xbrl.org/docs/api). L’ISIN est rapproché
   du LEI via l’API gratuite de [GLEIF](https://www.gleif.org/en/lei-data/gleif-api/).
   La capitalisation de marché reste issue de Yahoo Finance.

Les années issues de plusieurs fournisseurs sont fusionnées par exercice, selon
l’ordre de priorité ci-dessus. Un exercice déjà présent est actualisé lors d’un
nouvel import afin de compléter les nouveaux champs sans créer de doublon. Si
aucun fournisseur ne livre un exercice exploitable, l’import est refusé avec le
détail des sources essayées.

La devise des états financiers peut différer de la devise de cotation. Dans ce
cas, les cours historiques Yahoo Finance sont convertis dans la devise des
comptes avec la paire de change publique correspondante. La capitalisation de
fin d’exercice est calculée avec le dernier cours annuel et le nombre moyen
d’actions publié ; à défaut, le nombre d’actions actuel sert d’estimation.

## Banques, assurances et sociétés déficitaires

Les banques et assureurs sont détectés à partir de leur classification
sectorielle. Leurs données publiées sont importées, mais le **MK Score
industriel**, la valorisation standard et le MK Global Score sont marqués non
applicables. Ces entreprises présentent souvent leur bilan par ordre de
liquidité et ne publient pas les postes actif circulant, passif exigible ou
EBITDA selon le modèle des sociétés industrielles. Remplacer ces postes par des
zéros ou par le total du bilan produirait des ratios artificiels.

L’affichage reste identique à celui des autres entreprises. Les cartes et
colonnes non alimentées sont conservées avec la valeur `N/A`, ce qui garantit
une lecture stable tout en distinguant clairement absence de publication et
valeur nulle.

Les pertes, EBIT ou EBITDA négatifs ne sont pas traités comme des données
manquantes. Ils sont conservés ; une règle dont le dénominateur est nul ou
négatif reçoit un statut défavorable au lieu de devenir artificiellement
favorable.

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

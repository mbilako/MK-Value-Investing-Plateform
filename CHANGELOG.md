# Changelog

## Unreleased

### Added

- Première version du moteur de sélection sectoriel : classification GICS en
  11 secteurs, persistance du secteur et de l’activité, classement par
  percentiles et Top 5 expliqué dans l’interface.
- Modèle relatif propre aux banques et assureurs fondé sur le ROE, les fonds
  propres rapportés à l’actif, le PER et la croissance du résultat.
- Route authentifiée `GET /api/v1/screener`, chargée en trois requêtes groupées
  afin de rester adaptée à un univers étendu.
- Action `POST /api/v1/screener/prepare` pour rétro-remplir les classifications
  et importer les historiques manquants par lots bornés, avec résultat détaillé
  par entreprise.

### Changed

- L’import financier automatique conserve désormais le secteur GICS normalisé
  et l’activité remontés par la source publique.
- L’écran de sélection permet de lancer le classement de l’univers et le
  chargement de dix historiques manquants sans quitter le Top 5.

## 0.12.0 - 2026-08-14

### Sprint 1H — indices européens et américains, tranche 1

- Ajoute l’ATHEX Composite, indice de référence grec à 60 composantes, depuis
  la composition publique paginée d’Euronext Athens et résout ses symboles sur
  leur cotation athénienne `.AT`.
- Livre la tranche 2 ciblée : DAX 40, FTSE 100, IBEX 35, FTSE MIB, SMI et
  Dow Jones, sans Euro Stoxx 50, STOXX Europe 600 ni famille Russell.
- Classe le catalogue par zone, puis par pays, et trie les pays et indices par
  ordre alphabétique français.
- Lit les positions publiques iShares/BlackRock pour l’Allemagne, le
  Royaume-Uni, l’Italie et la Suisse, le fichier quotidien State Street pour le
  Dow Jones et le référentiel BME pour l’IBEX 35.
- Résout les tickers européens sur leur place primaire (`.DE`, `.L`, `.MC`,
  `.MI`, `.SW`) avant l’ajout à l’univers.

- Organise l’explorateur en catalogue multi-fournisseurs par région.
- Ajoute les indices européens AEX, BEL 20, PSI et ISEQ 20 depuis les
  compositions publiques Euronext.
- Ajoute le S&P 500 depuis les positions publiques de l’iShares Core S&P 500
  ETF et le Nasdaq-100 depuis l’API publique Nasdaq.
- Accepte les composantes identifiées directement par ticker lorsque l’ISIN
  n’est pas publié, avec devise USD et place de cotation américaine.
- Porte l’ajout multiple à 600 titres et étend l’audit aux neuf indices, soit
  721 lignes de cotation uniques au contrôle du 5 août 2026.

- Simplifie le parcours principal autour de l’explorateur d’indices et retire
  l’import manuel d’entreprise de l’interface.
- Charge jusqu’à dix exercices publics, complète les années manquantes sans
  doublon et calcule un MK Score distinct pour chaque année applicable.
- Uniformise l’analyse autour d’un tableau fondamental décennal pour les
  sociétés industrielles, les banques et les assureurs.
- Active les entrées de navigation Entreprises, Analyses, Règles et Journal ;
  le Journal présente les analyses récentes.
- Étend l’historique avec le résultat avant impôt, le cours de clôture, les
  actions en circulation, les actions autodétenues et le flux de trésorerie
  d’investissement.
- Uniformise les cartes et le tableau pour tous les secteurs ; les blocs et
  colonnes peuvent être déplacés à gauche ou à droite et leur ordre est
  mémorisé dans le navigateur.
- Remplace le panneau de ratios détaillés par les fondamentaux, tendances et
  ratios demandés directement visibles.
- Remplace la dette nette du panneau principal par le cours de clôture au
  31 décembre et renomme la valeur économique des capitaux propres par action
  sans afficher sa formule.
- Accepte les exercices précommerciaux sans revenus, les capitaux propres
  négatifs et les capitalisations temps réel indisponibles ; le CapEx peut
  être reconstitué à partir du flux opérationnel et du Free Cash Flow publié.
- Ajoute un audit reproductible des compositions d’indices et valide les
  120 composantes actuelles du SBF 120 avec au moins un exercice exploitable.

- Corrige la couverture financière de BNP Paribas, Société Générale, Crédit
  Agricole, AXA, SCOR, Worldline et Maurel & Prom : profils financiers
  sectoriels, pertes conservées, aliases Yahoo/ESEF étendus et conversion de
  devise de la capitalisation.
- Empêche les collisions entre tickers Euronext suffixés et homonymes SEC
  américains, notamment `ACA.PA` et `ACA`.
- Désactive explicitement le MK Score industriel et la valorisation standard
  pour les banques et assureurs afin d'éviter des ratios artificiels.

### Added

- Espace Favoris persistant, disponible également pour les banques et
  assureurs sans MK Score, sans doublon dans l’univers d’investissement.
- Comparaison des deux derniers exercices avec EBITDA, marges, décote,
  rendement action-obligation, levier et niveau d’endettement.
- Modification, archivage réversible et suppression définitive des entreprises
  depuis le portefeuille de recherche et l’univers d’investissement.
- Explorateur des compositions CAC 40, CAC Next 20 et SBF 120 avec sélection
  multiple, résolution automatique du ticker et ajout idempotent à l’univers.
- Identifiants stables ISIN, CIK et LEI, symboles par fournisseur et badges
  d’appartenance aux indices.
- Repli automatique par exercice annuel complet entre Yahoo Finance, SEC EDGAR
  et les dépôts européens ESEF gratuits exposés par filings.xbrl.org et GLEIF.

- Configuration Docker Compose dédiée à un VPS avec HTTPS automatique Caddy,
  réseaux privés et secrets montés comme fichiers.
- Endpoint `/api/v1/ready` vérifiant réellement PostgreSQL, identifiants de
  requête et journaux d’accès JSON.
- Runbook de déploiement, sauvegarde, restauration, diagnostic et retour
  arrière pour l’exploitation sur une VM Linux.

### Changed

- L’import public automatique n’est plus lié à Yahoo Finance : la provenance
  de la source effectivement retenue est enregistrée dans chaque snapshot.
- Les entreprises archivées sont masquées par défaut sans perdre leurs
  analyses ; une suppression définitive conserve une confirmation explicite.

- Le frontend de production applique des en-têtes HTTP de sécurité et une
  limitation périphérique des routes d’authentification.
- Les migrations Alembic sont exécutées par un service ponctuel avant le
  démarrage du backend.

### Security

- La déconnexion échoue désormais de manière fermée : si la révocation serveur
  n’est pas confirmée, l’espace authentifié reste visible avec une alerte
  persistante et une nouvelle tentative reste possible.
- Le démarrage en mode production refuse les valeurs de développement, les
  origines non HTTPS, les cookies non sécurisés et les secrets manquants.
- PostgreSQL et l’API ne publient aucun port directement sur le VPS ; seul
  Caddy expose HTTP et HTTPS.

## 0.11.0 - 2026-08-02

### Added

- Authentification multifacteur TOTP avec application d’authentification.
- Huit codes de récupération à usage unique, affichés une seule fois lors de
  l’activation du MFA.
- Écran de sécurité permettant d’activer ou désactiver le MFA, de consulter
  les sessions actives et de révoquer un appareil ou toutes les autres
  sessions.
- Migration PostgreSQL dédiée aux secrets MFA chiffrés, codes de récupération,
  compteurs de connexion et métadonnées de session.

### Changed

- Le parcours de connexion crée une session uniquement après la validation du
  second facteur lorsqu’il est activé.
- L’activité d’une session est actualisée au plus une fois toutes les cinq
  minutes afin de conserver une information utile sans écrire à chaque appel.
- Un lien de réinitialisation invalide permet désormais de revenir clairement
  à l’écran de connexion.

### Security

- Secrets TOTP chiffrés avec Fernet et clé dédiée validée au démarrage.
- Limitation atomique des tentatives de connexion et de MFA par IP et par
  compte, avec fenêtres configurables.
- Réponses de connexion génériques lorsque les identifiants ou les limites
  sont invalides, afin de ne pas révéler l’état d’un compte.
- Désactivation du MFA protégée par un code TOTP ou un code de récupération
  valide ; les codes restants sont supprimés après désactivation.

## 0.10.0 - 2026-07-28

### Added

- Vérification de l’adresse email obligatoire avant la première connexion.
- Réinitialisation du mot de passe avec révocation de toutes les sessions du
  compte.
- Prévisualisation locale des emails de vérification et de réinitialisation
  dans Mailpit.

### Changed

- Le premier compte humain vérifié reprend atomiquement les entreprises
  historiques ; une simple inscription non vérifiée ne revendique plus ces
  données.

### Security

- Jetons de vérification et de réinitialisation aléatoires, à usage unique et
  conservés en base uniquement sous forme d’empreinte.
- Réponses génériques identiques pour les demandes d’inscription, de renvoi et
  de réinitialisation afin de ne pas révéler l’existence ou l’état d’un compte.
- Délai minimal et plafond horaire admis atomiquement pour chaque destinataire
  et chaque type d’email, y compris sous requêtes concurrentes.

## 0.9.1 - 2026-07-27

### Added

- Quota quotidien configurable pour les analyses IA, isolé par utilisateur.
- Cache persistant des réponses IA, isolé par utilisateur et invalidé lorsque
  le contexte MK-VIP ou la question change.
- Migration PostgreSQL dédiée aux compteurs de quota et au cache IA.

### Security

- Incrément atomique du quota afin que les requêtes concurrentes ne puissent
  pas dépasser la limite quotidienne.
- Réponse `429` avec en-tête `Retry-After` lorsque le quota est épuisé.
- Les réponses servies depuis le cache ne consomment pas de quota
  supplémentaire.
- Les appels Yahoo synchrones utilisent une capacité dédiée et bornée ; les
  requêtes excédentaires sont refusées avant d’atteindre l’exécuteur.
- Un délai de réponse par appel et un délai global par import empêchent une
  transaction distante de monopoliser indéfiniment une requête.
- Un utilisateur ne peut lancer qu’un import automatique à la fois et une
  entreprise ne peut avoir deux imports concurrents.

## 0.9.0 - 2026-07-26

### Added

- Création de compte, connexion, restauration de session et déconnexion.
- Sessions personnelles conservées côté serveur avec une durée configurable.
- Documentation de sécurité et de configuration dans
  [`docs/authentication.md`](docs/authentication.md).
- Validation PostgreSQL en CI de la migration v0.8 vers v0.9 et de la
  concurrence entre deux premières inscriptions.

### Changed

- Chaque entreprise et toutes ses analyses sont désormais rattachées à son
  propriétaire.
- Le premier compte créé reprend atomiquement les entreprises historiques ;
  les comptes suivants commencent avec un univers vide.
- L’interface affiche l’email du compte courant et un état dédié lorsque la
  session expire.

### Security

- Mots de passe hachés avec Argon2id et verrouillage temporaire après cinq
  échecs de connexion.
- Cookie de session `HttpOnly`, `SameSite=Strict`, limité à `/api` et
  configurable avec `Secure` obligatoire derrière HTTPS en production.
- Validation de l’origine des écritures et CORS limité aux origines
  explicitement autorisées.
- Les UUID appartenant à un autre compte répondent `404` sans divulguer
  l’existence des données.

## 0.8.0 - 2026-07-26

### Added

- Analyste IA en trois modes : synthèse, comparaison et question naturelle.
- Route `POST /api/v1/ai/analyses` avec contrat de sortie structuré.
- Fournisseur OpenAI interchangeable fondé sur l’API Responses.
- Citations obligatoires vers les analyses financières, valorisations et
  scorings MK-VIP transmis au modèle.
- Tiroir responsive présentant conclusion, constats, risques, informations
  manquantes, sources et avertissement.

### Security

- Clé OpenAI chargée depuis l’environnement et exclue du dépôt Git.
- Aucun accès Web ou outil externe accordé au modèle.
- Rejet des citations absentes du contexte et interdiction explicite des
  recommandations d’achat, de vente ou d’allocation.
- Les valeurs du contexte JSON sont traitées comme des données, jamais comme
  des instructions.

## 0.7.0 - 2026-07-26

### Added

- Tableau de décision agrégeant le dernier scoring de chaque entreprise.
- Distribution des signaux « Profil favorable », « À approfondir »,
  « Prudence » et « À scorer ».
- Portefeuille de recherche trié par score global, avec écart de valeur et
  composante la plus faible.
- Filtre par signal et ouverture directe de l’analyse détaillée.
- Recherche de l’univers d’investissement par nom ou ticker.
- Route API `GET /api/v1/dashboard` et contrat typé associé.

### Changed

- Le résumé affiche les profils favorables à la place d’une alerte fictive.
- Le tableau est explicitement présenté comme un univers de recherche, sans
  inventer de positions, quantités, prix de revient ou performances.

## 0.6.0 - 2026-07-26

### Added

- Scoring global explicable composé à parts égales de la qualité, de la
  sécurité, de la valeur et d’un proxy quantitatif de moat.
- Signaux de présélection « Profil favorable », « À approfondir » et
  « Prudence », avec garde-fou sur les composantes faibles.
- Quatre explications persistées, détail des poids et contributions, et
  historique des calculs par entreprise.
- Routes API de création et de lecture des scorings.
- Panneau responsive intégré au tiroir d’analyse après la valorisation.
- Migration PostgreSQL dédiée au Scoring Engine.

## 0.5.0 - 2026-07-26

### Added

- Cinq méthodes de valorisation explicables : DCF, Buffett Owner Earnings,
  Earnings Power Value, formule de Graham et multiple de résultat.
- Scénarios persistés avec hypothèses, résultat central, marge de sécurité et
  écart avec la capitalisation observée.
- Routes API de création et d’historique des valorisations par entreprise.
- Formulaire responsive intégré au tiroir d’analyse, avec détail de chaque
  méthode et de ses limites.
- Migration PostgreSQL dédiée au Valuation Engine.

## 0.4.0 - 2026-07-26

### Added

- Six indicateurs financiers : Free Cash Flow, marge de Free Cash Flow, ROE,
  ROIC, couverture des intérêts et dette nette.
- Scores spécialisés de qualité et de sécurité en complément du MK Score.
- Historique financier par entreprise et calcul des croissances pluriannuelles.
- Tiroir d’analyse responsive avec indicateurs, tendances, source et limites.
- Migration PostgreSQL du Financial Engine avec reprise des snapshots existants.

### Changed

- Le contrat fournisseur normalisé inclut désormais le flux de trésorerie
  opérationnel.

## 0.3.0 - 2026-07-26

### Added

- Interface commune `FinancialDataProvider` pour découpler les sources du
  moteur d’analyse.
- Premier connecteur Yahoo Finance sans clé API.
- Recherche d’entreprises, profils, états annuels et historique de prix
  normalisés par le fournisseur Yahoo.
- Import automatique du dernier exercice annuel complet depuis le tableau de
  bord.
- Messages d’erreur lisibles lorsque la source est indisponible ou incomplète.

### Changed

- Le client API restitue désormais le détail des erreurs du backend.
- L’import manuel reste disponible comme solution de contrôle et de repli.

## 0.2.0 - 2026-07-25

### Added

- Import de snapshots financiers annuels normalisés.
- Calcul automatique de dix ratios et du MK Score.
- Historisation PostgreSQL avec unicité par entreprise et exercice.
- Parcours d’interface « Ajouter les données » pour les entreprises en attente.
- Affichage du statut d’analyse et du MK Score dans l’univers d’investissement.

## 0.1.0 - 2026-07-25

### Added

- Socle monorepo de MK-VIP.
- API FastAPI de santé et de gestion des entreprises.
- Modèle PostgreSQL et première migration Alembic.
- Catalogue initial de règles d’investissement issu du classeur métier.
- Tableau de bord React responsive et parcours d’import d’Air Liquide.
- Tests automatisés backend et frontend.
- Docker Compose et intégration continue GitHub Actions.

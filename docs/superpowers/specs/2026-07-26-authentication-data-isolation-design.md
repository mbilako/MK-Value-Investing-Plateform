# MK-VIP v0.9 — Authentification et isolation des données

Date : 26 juillet 2026
Statut : conception approuvée

## 1. Objectif

La v0.9 transforme MK-VIP en application réellement multi-utilisateur. Chaque personne dispose d’un compte personnel et d’un espace de travail strictement isolé. Cette fondation prépare le Journal IA et une future distribution de la plateforme.

Le périmètre comprend :

- inscription libre par email et mot de passe ;
- connexion, maintien de session et déconnexion ;
- sessions opaques conservées côté serveur ;
- protection de toutes les fonctions métier ;
- propriété explicite des entreprises par un utilisateur ;
- isolation des données financières, valorisations, scores et analyses IA ;
- reprise automatique des données de démonstration existantes par le premier compte ;
- interface de connexion et gestion des sessions expirées.

## 2. Hors périmètre

Les fonctions suivantes sont volontairement reportées à une version ultérieure :

- vérification de l’adresse email ;
- mot de passe oublié et réinitialisation ;
- connexion avec Google, Apple ou un autre fournisseur ;
- authentification multifacteur ;
- gestion d’équipes ou partage de portefeuilles ;
- rôles administrateur ;
- suppression autonome du compte ;
- défense distribuée contre les abus d’inscription et de connexion.

Avant une ouverture publique à grande échelle, une limitation de débit au niveau de l’infrastructure et la vérification des emails devront compléter les protections de cette version.

## 3. Décision d’architecture

### 3.1 Approche retenue

MK-VIP utilisera des sessions opaques conservées dans la base de données. Le navigateur ne recevra qu’un jeton aléatoire dans un cookie sécurisé. La base ne conservera qu’une empreinte irréversible de ce jeton.

Cette approche est retenue car elle :

- permet de révoquer immédiatement une session ;
- garde la logique de sécurité côté serveur ;
- évite d’exposer des informations utilisateur dans un jeton lisible ;
- convient à l’architecture FastAPI et React actuelle ;
- reste simple à faire évoluer vers une liste d’appareils ou une révocation globale.

### 3.2 Approches écartées

- **JWT avec jetons d’accès et de renouvellement** : plus de complexité pour la révocation, la rotation et la gestion des jetons volés, sans avantage nécessaire pour la v0.9.
- **Fournisseur d’identité externe** : robuste mais ajoute une dépendance, des coûts et une expérience moins maîtrisée alors que l’email et le mot de passe suffisent au périmètre actuel.

## 4. Modèle de données

### 4.1 Utilisateurs

Une table `users` contiendra au minimum :

- `id` : UUID, clé primaire ;
- `email` : adresse normalisée, unique ;
- `password_hash` : empreinte Argon2id du mot de passe ;
- `is_active` : autorise ou interdit la connexion ;
- `is_system` : distingue le propriétaire technique temporaire des comptes humains ;
- `failed_login_attempts` : nombre d’échecs consécutifs ;
- `locked_until` : fin éventuelle du verrouillage temporaire ;
- `created_at` et `updated_at`.

L’adresse est normalisée en supprimant les espaces périphériques et en utilisant une casse uniforme avant toute comparaison. Le mot de passe en clair ne doit jamais être enregistré, journalisé ou renvoyé par l’API.

### 4.2 Sessions

Une table `sessions` contiendra :

- `id` : UUID, clé primaire ;
- `user_id` : propriétaire de la session ;
- `token_hash` : empreinte SHA-256 unique du jeton aléatoire ;
- `created_at` ;
- `expires_at`.

La suppression d’un utilisateur supprime ses sessions. Une déconnexion supprime la session correspondante. Les sessions expirées sont refusées même si leur nettoyage physique n’a pas encore eu lieu.

### 4.3 Propriété des entreprises

La table `companies` recevra un champ `owner_id` obligatoire relié à `users.id`.

L’unicité actuelle du symbole boursier devient une unicité composée :

```text
(owner_id, ticker)
```

Deux utilisateurs peuvent donc suivre la même entreprise, mais un utilisateur ne peut pas ajouter deux fois le même symbole dans son propre espace.

Les données financières, valorisations et scores restent reliés à leur entreprise. Elles héritent de sa propriété. Les services et requêtes doivent néanmoins inclure explicitement l’utilisateur courant dans chaque recherche afin qu’aucun identifiant connu ne permette de franchir cette frontière.

Les référentiels globaux éventuels, comme le catalogue des règles d’investissement, ne reçoivent pas de propriétaire, mais leur API reste réservée aux utilisateurs connectés.

## 5. Migration des données existantes

La migration suit deux étapes sûres :

1. créer un utilisateur système non connectable et lui attribuer toutes les entreprises existantes ;
2. lors de la première inscription humaine, transférer toutes ces entreprises au nouveau compte puis supprimer le propriétaire système devenu inutile.

Le transfert de la première inscription est exécuté dans une transaction unique. Il doit être sérialisé afin que deux inscriptions simultanées ne puissent pas réclamer les mêmes données. En cas d’échec, aucun transfert partiel n’est conservé.

Comme les données financières, valorisations et scores sont reliés aux entreprises, le changement de propriétaire des entreprises transfère tout l’historique associé sans le recopier.

Le résultat attendu est :

- le premier compte reçoit Air Liquide, L’Oréal et Danone ainsi que leurs données associées ;
- tous les comptes suivants commencent avec un espace vide ;
- aucune donnée existante n’est perdue ou dupliquée.

## 6. API d’authentification

Les routes suivantes seront ajoutées sous `/api/v1/auth` :

### `POST /register`

- accepte un email et un mot de passe ;
- exige un mot de passe de 12 à 128 caractères ;
- refuse un email déjà inscrit ;
- crée le compte et sa première session dans la même opération ;
- déclenche, si nécessaire, la reprise transactionnelle des données historiques ;
- installe le cookie de session ;
- renvoie le profil public du compte.

### `POST /login`

- recherche l’utilisateur à partir de l’email normalisé ;
- vérifie le mot de passe sans différence de message entre un email inconnu, un mauvais mot de passe, un compte inactif ou un compte verrouillé ;
- réinitialise le compteur après une connexion réussie ;
- crée une nouvelle session et installe son cookie.

Après cinq échecs consécutifs, le compte est verrouillé pendant quinze minutes. La réponse reste générique pour ne pas confirmer l’existence d’un compte.

### `GET /me`

- renvoie le profil de l’utilisateur associé à la session ;
- renvoie `401` si la session est absente, expirée, révoquée ou rattachée à un compte inactif.

### `POST /logout`

- supprime la session active si elle existe ;
- efface le cookie côté navigateur ;
- reste sans danger lorsqu’aucune session valide n’est présente.

## 7. Politique de session et protections

Le jeton de session contient au moins 256 bits d’aléa cryptographique. Sa valeur brute n’existe que dans le cookie du navigateur ; seule son empreinte SHA-256 est recherchée dans la base.

Le cookie :

- se nomme `mkvip_session` ;
- est `HttpOnly` ;
- utilise `SameSite=Strict` ;
- est limité au chemin de l’API ;
- expire après 30 jours ;
- utilise `Secure` en production et une configuration compatible avec le développement local.

La durée de 30 jours est fixe à partir de la connexion ; une simple activité ne la prolonge pas. Une nouvelle connexion crée une session distincte.

Les requêtes d’écriture contrôlent également leur origine. La liste d’origines autorisées reste explicite et les appels avec cookies activent les règles CORS adaptées. Les mots de passe et jetons bruts sont exclus des journaux.

## 8. Autorisation et isolation

Seules les routes suivantes restent publiques :

- contrôle de santé du service ;
- inscription ;
- connexion.

Le tableau de bord, les entreprises, imports, données financières, analyses, valorisations, scores, règles d’investissement et fonctions IA nécessitent une session valide.

Pour chaque ressource rattachée à une entreprise, la recherche combine :

```text
identifiant de la ressource + propriétaire courant
```

Une ressource appartenant à un autre utilisateur renvoie `404`, comme une ressource inexistante. Cette règle évite de révéler l’existence ou le contenu des données d’un autre compte.

La création et la modification vérifient également la propriété de toutes les ressources parentes. L’Analyste IA ne peut recevoir et exploiter qu’une entreprise appartenant à l’utilisateur connecté.

L’isolation doit être assurée dans la couche de services et les requêtes de données, et non uniquement dans l’interface.

## 9. Expérience utilisateur

### 9.1 Démarrage

Au chargement de l’application, le frontend appelle `/auth/me` avant de charger les données métier.

Trois états explicites sont prévus :

- vérification de session en cours ;
- utilisateur non connecté ;
- utilisateur connecté.

Un écran de chargement dédié empêche l’apparition brève du tableau de bord avant la fin de la vérification.

### 9.2 Inscription et connexion

L’écran non connecté propose deux vues cohérentes :

- « Se connecter » ;
- « Créer un compte ».

Après une inscription ou une connexion réussie, le tableau de bord personnel est chargé automatiquement. Les erreurs de formulaire sont compréhensibles, accessibles et ne révèlent pas d’informations sensibles.

Le style reprend l’identité actuelle bleu nuit et émeraude. Les formulaires restent utilisables sur ordinateur et mobile.

### 9.3 Session active

L’en-tête affiche l’adresse email et une action « Se déconnecter ». Tous les appels API envoient les cookies de session.

Si une requête renvoie `401`, le frontend :

1. efface son état d’authentification ;
2. revient à l’écran de connexion ;
3. affiche un message indiquant que la session a expiré.

Une erreur métier sans rapport avec l’authentification ne doit pas déconnecter l’utilisateur.

### 9.4 Premier compte et comptes vides

Le premier compte retrouve immédiatement les données historiques. Un compte ultérieur sans entreprise voit un état vide accompagné d’une action claire pour ajouter sa première entreprise.

## 10. Gestion des erreurs

- `400` : données de formulaire invalides lorsque le détail peut être communiqué sans risque ;
- `401` : session absente ou invalide, ou échec de connexion avec message générique ;
- `404` : ressource inexistante ou appartenant à un autre utilisateur ;
- `409` : email déjà utilisé à l’inscription ou symbole déjà suivi par le même utilisateur ;
- `422` : structure de requête invalide selon les règles de validation de l’API.

Les erreurs internes ne doivent exposer ni requête SQL, ni empreinte, ni secret, ni détail permettant d’identifier un autre compte.

## 11. Stratégie de tests

### 11.1 Backend

Les tests automatisés couvrent au minimum :

- inscription valide et connexion automatique ;
- normalisation et unicité des emails ;
- validation de la longueur du mot de passe ;
- connexion valide et erreur générique en cas d’échec ;
- verrouillage après cinq échecs et déverrouillage après quinze minutes ;
- réinitialisation du compteur après une réussite ;
- création, expiration et déconnexion d’une session ;
- refus d’une session rattachée à un compte inactif ;
- protection de chaque famille de routes métier ;
- lecture, création, modification et suppression limitées au propriétaire ;
- réponse `404` pour un identifiant appartenant à un autre compte ;
- même symbole autorisé pour deux propriétaires mais interdit deux fois pour le même ;
- isolation du tableau de bord, des analyses et de l’Analyste IA ;
- transfert des données historiques au premier compte seulement ;
- atomicité du transfert lorsque l’opération échoue.

Les anciens tests métier utilisent désormais une session authentifiée explicite. Aucun test ne dépend d’un véritable envoi d’email ou d’un appel OpenAI réel.

### 11.2 Frontend

Les tests couvrent :

- écran de chargement pendant `/auth/me` ;
- affichage de la connexion sans session ;
- bascule entre connexion et inscription ;
- inscription et connexion réussies ;
- chargement des données après authentification ;
- affichage de l’utilisateur et déconnexion ;
- retour à la connexion après un `401` ;
- conservation des erreurs métier ordinaires sans déconnexion ;
- état vide d’un nouveau compte.

### 11.3 Validation globale

La livraison exige :

- réussite des tests backend et frontend ;
- réussite des contrôles de style et de types ;
- migration montante validée sur une base contenant les données actuelles ;
- vérification visuelle sur ordinateur et mobile ;
- absence de secret ou de mot de passe dans le dépôt et les journaux ;
- documentation de configuration mise à jour.

## 12. Critères d’acceptation

La v0.9 est acceptée si :

1. un visiteur peut créer un compte, se connecter et se déconnecter ;
2. une session reste utilisable après un rechargement puis expire au bout de 30 jours ;
3. aucun appel métier n’est accessible sans session ;
4. deux comptes ne peuvent ni découvrir ni manipuler leurs données respectives ;
5. deux comptes peuvent suivre le même symbole indépendamment ;
6. le premier compte récupère les données historiques et les suivants démarrent vides ;
7. l’Analyste IA respecte la même frontière de propriété ;
8. une session expirée est gérée proprement dans l’interface ;
9. l’ensemble des tests et validations définis ci-dessus réussit.

## 13. Séquencement de réalisation

L’implémentation sera conduite par les tests dans l’ordre général suivant :

1. modèles et migration des utilisateurs, sessions et propriétaires ;
2. primitives de mot de passe et de session ;
3. API d’inscription, connexion, profil et déconnexion ;
4. dépendance d’authentification commune ;
5. isolation progressive de toutes les fonctions métier ;
6. état d’authentification et écrans frontend ;
7. gestion globale des sessions expirées ;
8. documentation, vérifications de sécurité et validation complète.

Le plan d’implémentation détaillé sera produit séparément après validation de cette spécification écrite.

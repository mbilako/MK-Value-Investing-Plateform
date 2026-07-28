# Sprint 1D — Vérification d’email et réinitialisation du mot de passe

**Statut :** conception approuvée

**Version cible :** MK-VIP 0.10.0

**Date :** 2026-07-28

## Contexte

MK-VIP 0.9.1 dispose de comptes personnels, de sessions serveur, d’un
verrouillage après échecs de connexion et d’une isolation des données par
propriétaire. Un nouveau compte peut cependant utiliser immédiatement une
adresse non vérifiée et aucun parcours ne permet de récupérer un mot de passe
oublié.

Le Sprint 1D ajoute ces deux parcours sur une infrastructure commune de jetons
temporaires et d’emails. Les emails sont prévisualisés localement avec Mailpit ;
aucun fournisseur externe n’est intégré dans cette version.

## Objectifs

- Exiger la vérification de l’adresse avant toute connexion d’un nouveau compte.
- Préserver l’accès des comptes humains créés avant la migration.
- Permettre de demander et confirmer une réinitialisation de mot de passe.
- Utiliser des jetons à usage unique, expirables, révocables et stockés
  uniquement sous forme d’empreinte.
- Ne pas révéler si une adresse est inscrite lors d’une demande ou d’un renvoi.
- Limiter les demandes à une par minute et cinq par heure pour une même adresse
  et un même usage.
- Révoquer toutes les sessions après une réinitialisation réussie.
- Prévisualiser les emails dans Mailpit avec un transport SMTP remplaçable.
- Conserver le transfert sécurisé des entreprises historiques au premier compte
  humain réellement vérifié.

## Hors périmètre

- Envoi d’emails par un fournisseur de production.
- File d’emails durable et reprise automatique après arrêt du processus.
- Authentification multifacteur, fournisseurs sociaux ou clés d’accès.
- Changement d’adresse email et changement de mot de passe depuis une session.
- Limitation distribuée par adresse IP ou protection anti-bot.
- Limites Yahoo distribuées entre plusieurs instances.

## Décisions de produit

- Les nouveaux comptes ne reçoivent aucune session lors de l’inscription.
- Un compte non vérifié ne peut pas se connecter.
- Les comptes humains existants sont marqués comme vérifiés par la migration.
- Le lien de vérification expire après 24 heures.
- Le lien de réinitialisation expire après 30 minutes.
- Un nouveau jeton invalide les jetons actifs précédents du même usage.
- Après vérification, l’utilisateur revient à la connexion sans session
  automatique.
- Après réinitialisation, toutes les sessions sont supprimées et l’utilisateur
  doit se reconnecter.
- Une réinitialisation ne vérifie pas implicitement l’adresse email.
- Les demandes génériques répondent de la même manière pour une adresse connue,
  inconnue, déjà vérifiée ou limitée.

## Architecture

### Composants

`AuthService` reste responsable des transitions de compte, des jetons et des
sessions. Il reçoit deux nouvelles dépendances :

- un générateur de jetons cryptographiquement aléatoires ;
- un calculateur HMAC pour la clé de limitation par adresse.

Un composant `EmailSender` porte l’interface de livraison :

```python
class EmailSender(Protocol):
    def send_verification_email(self, recipient: str, token: str) -> None: ...
    def send_password_reset_email(self, recipient: str, token: str) -> None: ...
```

`SmtpEmailSender` construit les URLs publiques, rend des emails texte et HTML,
puis utilise SMTP avec un délai réseau borné. Les tests injectent un
`RecordingEmailSender` sans accès réseau.

Les routes FastAPI planifient les appels synchrones de `EmailSender` dans
`BackgroundTasks`. La réponse générique est donc envoyée avant la connexion
SMTP. Un échec de livraison est journalisé sans jeton, mot de passe ni adresse
complète. L’utilisateur peut refaire une demande après le délai autorisé.

### Modèle de données

La migration `20260728_0008_add_account_recovery.py` ajoute :

#### `users.email_verified_at`

- `TIMESTAMP WITH TIME ZONE`, nullable ;
- rempli à la date de migration pour tous les utilisateurs non système
  existants ;
- laissé vide pour le propriétaire système historique et les nouveaux comptes.

#### `auth_action_tokens`

- `id UUID`, clé primaire ;
- `user_id UUID`, clé étrangère vers `users.id` avec suppression en cascade ;
- `purpose VARCHAR(32)`, limité par contrainte à `email_verification` ou
  `password_reset` ;
- `token_hash VARCHAR(64)`, unique et indexé ;
- `created_at`, `expires_at` et `consumed_at` en UTC ;
- index sur `(user_id, purpose, consumed_at)` et sur `expires_at`.

Le jeton brut contient 32 octets aléatoires encodés pour URL. Seule son
empreinte SHA-256 est persistée. La consommation verrouille la ligne, vérifie
son usage, son expiration et son état, puis renseigne `consumed_at` dans la même
transaction que l’action métier.

#### `auth_email_rate_limits`

- `id UUID`, clé primaire ;
- `recipient_hash VARCHAR(64)` ;
- `purpose VARCHAR(32)` ;
- `window_start TIMESTAMP WITH TIME ZONE`, arrondi à l’heure UTC ;
- `request_count INTEGER` ;
- `last_requested_at TIMESTAMP WITH TIME ZONE` ;
- contrainte unique sur `(recipient_hash, purpose, window_start)`.

`recipient_hash` est un HMAC-SHA-256 de l’adresse normalisée avec
`MKVIP_AUTH_EMAIL_HASH_SECRET`. La mise à jour est atomique : elle autorise une
demande seulement si la précédente date d’au moins 60 secondes et si le
compteur horaire est inférieur à 5. Les lignes antérieures à 24 heures et les
jetons expirés ou consommés depuis plus de 7 jours sont supprimés
opportunément lors d’une nouvelle émission.

## Parcours métier

### Inscription

1. Le client envoie l’adresse et le mot de passe à `POST /auth/register`.
2. Pour une nouvelle adresse, le service crée un utilisateur non vérifié, sans
   session, puis crée un jeton de vérification valable 24 heures.
3. Pour un compte non vérifié existant, le mot de passe n’est pas modifié ; un
   nouveau lien peut être émis si la limite le permet.
4. Pour un compte vérifié existant, aucun email n’est envoyé.
5. Tous les cas répondent `202` avec le même message.
6. Lorsque l’émission est autorisée, la route planifie l’email Mailpit.

Ce comportement remplace la réponse `409` sur adresse existante afin de réduire
l’énumération de comptes.

### Vérification

1. L’email pointe vers `/#verify-email=<jeton>`.
2. Le frontend lit puis efface immédiatement le fragment de l’historique.
3. Il envoie le jeton à `POST /auth/verify-email`.
4. Le service verrouille et consomme le jeton, puis renseigne
   `email_verified_at`.
5. Dans la même transaction, il verrouille le propriétaire système historique.
   S’il existe encore, ses entreprises sont transférées à ce compte vérifié,
   puis le propriétaire système est supprimé.
6. Le frontend confirme la vérification et propose le retour à la connexion.

Deux vérifications concurrentes ne peuvent ni consommer le même jeton ni
revendiquer deux fois les entreprises historiques.

### Renvoi de vérification

`POST /auth/resend-verification` accepte une adresse et répond toujours `202`.
Un jeton est émis uniquement pour un compte humain actif et non vérifié, sous
réserve des limites. Les anciens jetons de vérification non consommés sont
invalidés.

### Demande de réinitialisation

`POST /auth/password-reset/request` accepte une adresse et répond toujours
`202`. Un jeton de 30 minutes est émis uniquement pour un compte humain actif,
sous réserve des limites. Un compte non vérifié peut recevoir ce lien, mais la
réinitialisation ne change pas `email_verified_at`.

### Confirmation de réinitialisation

1. L’email pointe vers `/#reset-password=<jeton>`.
2. Le frontend efface le fragment et demande deux fois le nouveau mot de passe.
3. `POST /auth/password-reset/confirm` consomme le jeton et remplace le hachage
   Argon2id dans une transaction.
4. Toutes les lignes `sessions` de l’utilisateur sont supprimées dans cette
   transaction.
5. Le frontend confirme l’opération puis revient à la connexion.

## Contrat HTTP

### `POST /api/v1/auth/register`

Entrée :

```json
{"email": "investor@example.com", "password": "mot-de-passe-long"}
```

Réponse `202` :

```json
{"message": "Si cette adresse peut être inscrite, un email de vérification a été envoyé."}
```

### `POST /api/v1/auth/verify-email`

Entrée : `{"token": "<jeton>"}`.

Réponse : `204` sans session.

Erreurs : `400` pour un jeton invalide ou déjà consommé, `410` pour un jeton
expiré.

### `POST /api/v1/auth/resend-verification`

Entrée : `{"email": "investor@example.com"}`.

Réponse générique `202`, y compris lorsque la limite est atteinte.

### `POST /api/v1/auth/password-reset/request`

Entrée : `{"email": "investor@example.com"}`.

Réponse générique `202`, y compris lorsque la limite est atteinte.

### `POST /api/v1/auth/password-reset/confirm`

Entrée :

```json
{"token": "<jeton>", "password": "nouveau-mot-de-passe-long"}
```

Réponse : `204`.

Erreurs : `400` pour un jeton invalide ou déjà consommé, `410` pour un jeton
expiré et `422` pour un mot de passe non conforme.

### `POST /api/v1/auth/login`

Le contrat de succès reste inchangé pour un compte vérifié. Un mot de passe
correct associé à un compte non vérifié reçoit `403` avec un message demandant
la vérification de l’adresse. Les autres échecs continuent de répondre avec le
message générique existant.

## Interface utilisateur

`AuthScreen` devient un conteneur d’états et délègue les formulaires à des
composants ciblés :

- connexion et inscription ;
- attente et renvoi de vérification ;
- résultat de la vérification ;
- demande de réinitialisation ;
- saisie du nouveau mot de passe ;
- résultat de la réinitialisation.

Les formulaires conservent l’identité visuelle actuelle et restent utilisables
au clavier et sur mobile. Les boutons sont désactivés pendant l’envoi, les
messages d’erreur sont associés aux formulaires et le focus est déplacé vers le
résultat après une transition.

Au démarrage, `App` examine `window.location.hash`. Un jeton reconnu est copié
en mémoire, puis l’URL est remplacée immédiatement avec
`history.replaceState`. Un fragment inconnu est ignoré sans appel API.

## Configuration locale

Les paramètres suivants sont ajoutés :

```dotenv
MKVIP_PUBLIC_APP_URL=http://localhost:5173
MKVIP_SMTP_HOST=mailpit
MKVIP_SMTP_PORT=1025
MKVIP_SMTP_FROM=MK-VIP <no-reply@mkvip.local>
MKVIP_SMTP_TIMEOUT_SECONDS=10
MKVIP_SMTP_STARTTLS=false
MKVIP_SMTP_USERNAME=
MKVIP_SMTP_PASSWORD=
MKVIP_AUTH_EMAIL_HASH_SECRET=change-me-outside-local-development
MKVIP_EMAIL_VERIFICATION_TTL_HOURS=24
MKVIP_PASSWORD_RESET_TTL_MINUTES=30
MKVIP_AUTH_EMAIL_COOLDOWN_SECONDS=60
MKVIP_AUTH_EMAIL_MAX_PER_HOUR=5
```

Docker Compose ajoute `axllent/mailpit` au réseau interne, expose uniquement
son interface web sur `8025` et laisse le SMTP accessible au backend sur
`1025`. La documentation de production impose HTTPS, un secret HMAC fort et un
transport SMTP authentifié avant tout envoi externe.

## Gestion des erreurs et observabilité

- Aucun jeton brut, mot de passe ou secret SMTP n’est journalisé.
- Les demandes génériques ne journalisent pas l’existence d’un utilisateur.
- Les échecs SMTP consignent le type d’email, l’identifiant interne de
  l’utilisateur lorsqu’il existe et la classe d’erreur.
- Les compteurs de succès, de limitation et d’échec de livraison restent des
  événements structurés ; aucune nouvelle plateforme d’observabilité n’est
  ajoutée dans ce sprint.
- Les tâches d’arrière-plan Mailpit ne sont pas durables. Ce compromis est
  accepté pour le mode local ; une file persistante sera requise avant un
  fournisseur de production.

## Stratégie de test

### Backend unitaire

- génération, empreinte, expiration et consommation unique des jetons ;
- invalidation des anciens jetons ;
- HMAC stable et isolé par secret ;
- limites d’une minute et de cinq demandes par heure ;
- suppression opportuniste des anciennes lignes ;
- rendu des deux types d’email avec liens corrects.

### API

- inscription sans cookie et réponse générique pour une adresse nouvelle ou
  existante ;
- refus de connexion avant vérification ;
- vérification réussie sans session ;
- renvoi et demande de reset sans énumération ;
- erreurs de jeton invalide, consommé et expiré ;
- réinitialisation avec révocation de toutes les sessions ;
- un compte non vérifié reste non vérifié après reset ;
- validation d’origine appliquée à toutes les nouvelles écritures.

### PostgreSQL

- migration montée et retour arrière ;
- comptes humains existants marqués comme vérifiés ;
- propriétaire système laissé non vérifié ;
- consommation atomique d’un jeton concurrent ;
- transfert unique des entreprises historiques entre deux vérifications
  concurrentes ;
- compteur horaire atomique sous demandes concurrentes.

### Frontend

- parcours inscription vers attente de vérification ;
- renvoi de l’email ;
- lecture et suppression du fragment de vérification ;
- connexion refusée avec accès au renvoi ;
- demande générique de réinitialisation ;
- lecture et suppression du fragment de reset ;
- confirmation du nouveau mot de passe et retour à la connexion ;
- accessibilité clavier et gestion du focus.

### Validation locale et CI

- `ruff`, `pytest`, ESLint, Vitest, TypeScript et build de production ;
- PostgreSQL 17 pour les migrations et tests concurrents ;
- `docker compose config` ;
- test manuel documenté : inscription, email visible dans Mailpit, vérification,
  demande de reset, second email visible, changement du mot de passe et
  reconnexion.

## Critères d’acceptation

Le Sprint 1D est terminé lorsque :

1. un nouveau compte ne peut pas se connecter avant vérification ;
2. les comptes antérieurs à la migration restent accessibles ;
3. les deux emails sont visibles dans Mailpit et leurs liens fonctionnent ;
4. les jetons sont hachés, expirables, à usage unique et révocables ;
5. les demandes génériques ne révèlent pas l’existence d’un compte ;
6. les limites convenues résistent aux accès concurrents ;
7. le premier compte vérifié revendique seul les données historiques ;
8. une réinitialisation supprime toutes les sessions ;
9. les migrations montée et retour arrière sont validées sur PostgreSQL 17 ;
10. les suites backend/frontend, le build et la CI sont entièrement verts.

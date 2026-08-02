# Authentification et isolation des données

MK-VIP v0.11 utilise des comptes personnels dont l’adresse email doit être
vérifiée. Toutes les routes métier exigent une session valide et chaque
entreprise appartient à un seul utilisateur.

## Sessions et cookie

Les sessions sont conservées côté serveur dans PostgreSQL. Le navigateur ne
reçoit qu’un identifiant aléatoire dont seule l’empreinte SHA-256 est stockée
en base. Le cookie `mkvip_session` est limité au chemin `/api`, inaccessible à
JavaScript (`HttpOnly`) et envoyé avec `SameSite=Strict`. Sa durée par défaut
est de 30 jours (`MKVIP_SESSION_DURATION_DAYS=30`).

La pile locale fonctionne en HTTP et utilise donc
`MKVIP_SESSION_COOKIE_SECURE=false`. En production, MK-VIP doit être servi
derrière HTTPS et `MKVIP_SESSION_COOKIE_SECURE=true` est obligatoire afin
d’ajouter l’attribut `Secure` au cookie.

L’inscription et la vérification ne créent jamais de session et ne déposent
aucun cookie. Une session est créée uniquement après une connexion réussie
d’un compte actif et vérifié. La confirmation d’un nouveau mot de passe
supprime toutes les sessions du compte : les cookies déjà présents ne
résolvent alors plus aucun utilisateur.

Le menu « Sécurité » liste les sessions non expirées, leur navigateur, leur
dernière activité et leur échéance. Une session précise peut être révoquée, ou
toutes les autres sessions peuvent l’être en une seule opération. La dernière
activité est actualisée au plus une fois toutes les cinq minutes afin d’éviter
une écriture en base à chaque requête authentifiée.

## Mots de passe et verrouillage

Les mots de passe ne sont jamais stockés en clair. Ils sont hachés avec
Argon2id par `pwdlib`. Après cinq échecs consécutifs
(`MKVIP_LOGIN_MAX_ATTEMPTS=5`), le compte est verrouillé pendant 15 minutes
(`MKVIP_LOGIN_LOCK_MINUTES=15`). Les échecs liés aux identifiants, à un compte
inactif ou à son verrouillage partagent la même réponse. Un mot de passe valide
sur un compte non vérifié reçoit une invitation explicite à vérifier l’adresse.

Les tentatives de connexion sont également admises atomiquement dans une
fenêtre partagée par PostgreSQL : 20 tentatives par IP et 10 par compte sur
15 minutes par défaut. Les mêmes compteurs protègent la validation MFA. Les
valeurs sont configurables avec `MKVIP_LOGIN_IP_MAX_PER_WINDOW`,
`MKVIP_LOGIN_ACCOUNT_MAX_PER_WINDOW` et
`MKVIP_LOGIN_RATE_LIMIT_WINDOW_MINUTES`. Une tentative refusée conserve la
réponse générique « Identifiants invalides ».

## Authentification multifacteur

Un compte connecté peut activer un second facteur depuis « Sécurité ». MK-VIP
génère un secret TOTP compatible avec les applications d’authentification
standard, puis exige un premier code à six chiffres avant d’activer le MFA.
Le secret temporaire expire après 10 minutes
(`MKVIP_MFA_PENDING_SETUP_TTL_MINUTES=10`).

Après activation, une connexion par email et mot de passe ne crée plus de
session immédiatement. Elle renvoie un défi à usage unique valable cinq
minutes (`MKVIP_MFA_CHALLENGE_TTL_MINUTES=5`). La session n’est créée qu’après
validation d’un code TOTP ou d’un code de récupération.

Huit codes de récupération sont générés par défaut
(`MKVIP_MFA_RECOVERY_CODE_COUNT=8`). Ils ne sont affichés qu’une fois, sont
conservés sous forme de hachage Argon2id et deviennent invalides dès leur
première utilisation. La désactivation du MFA exige un code TOTP ou de
récupération valide et supprime tous les codes restants.

Le secret TOTP est chiffré en base avec Fernet. La clé
`MKVIP_MFA_ENCRYPTION_KEY` doit être une clé Fernet URL-safe valide, distincte
pour chaque environnement et conservée dans le gestionnaire de secrets. La
perte ou le remplacement non planifié de cette clé rendrait les configurations
MFA existantes illisibles.

## Origines, CORS et requêtes d’écriture

`MKVIP_ALLOWED_ORIGINS` définit la liste JSON des origines autorisées, par
exemple `["http://localhost:5173"]`. Cette liste configure CORS avec les
identifiants autorisés et sert aussi à valider l’en-tête `Origin` de toute
requête d’écriture. Une origine absente ou non approuvée est refusée.

## Isolation par propriétaire

Chaque entreprise porte un `owner_id`. Toutes les lectures, créations et
analyses dérivées (snapshots financiers, valorisations, scorings, dashboard et
contexte IA) sont résolues dans le périmètre de l’utilisateur courant. Un UUID
valide appartenant à un autre compte reçoit volontairement la même réponse
`404` qu’un UUID inconnu afin de ne pas révéler son existence.

## Vérification et récupération de compte

`POST /api/v1/auth/register` crée un compte non vérifié et envoie un email
quand la demande est admissible. `POST /api/v1/auth/resend-verification`
permet de demander un nouveau lien. Dans les deux cas, la réponse est toujours
`202` avec le même corps :

```json
{
  "message": "Si cette adresse peut être inscrite, un email de vérification a été envoyé."
}
```

Cette réponse ne varie pas lorsque l’adresse existe déjà, lorsque son compte
est déjà vérifié, lorsqu’il n’est pas admissible ou lorsque la limite est
atteinte. Le lien contient le fragment `#verify-email=…`. Le frontend extrait
et retire ce fragment de l’historique du navigateur avant tout appel à
`POST /api/v1/auth/verify-email`. Un jeton valide répond `204`, un jeton
invalide ou déjà consommé `400`, et un jeton expiré `410`.

`POST /api/v1/auth/password-reset/request` répond toujours `202` avec :

```json
{
  "message": "Si cette adresse est inscrite, un email de réinitialisation a été envoyé."
}
```

Le statut et le corps restent identiques pour une adresse inconnue, inactive
ou limitée. Le lien contient `#reset-password=…`, fragment lui aussi retiré
avant tout appel API. `POST /api/v1/auth/password-reset/confirm` reçoit le
jeton et un nouveau mot de passe d’au moins 12 caractères. La confirmation
réussie répond `204`, consomme le jeton et révoque toutes les sessions du
compte ; les erreurs de jeton utilisent les mêmes statuts `400` et `410`.

Les jetons aléatoires ne sont envoyés qu’au destinataire et sont conservés en
base uniquement sous forme d’empreinte SHA-256. Ils sont à usage unique : un
nouveau renvoi invalide tout jeton encore actif du même compte et du même
usage. La durée de vie est exactement :

- vérification : 24 heures (`MKVIP_EMAIL_VERIFICATION_TTL_HOURS=24`) ;
- réinitialisation : 30 minutes
  (`MKVIP_PASSWORD_RESET_TTL_MINUTES=30`).

Chaque tentative d’envoi, même pour une adresse inconnue, est admise
atomiquement par destinataire et par usage. Le délai minimal est de
60 secondes (`MKVIP_AUTH_EMAIL_COOLDOWN_SECONDS=60`) et le plafond de
5 demandes dans une fenêtre horaire
(`MKVIP_AUTH_EMAIL_MAX_PER_HOUR=5`). Le destinataire est indexé par un HMAC
SHA-256, jamais par son adresse en clair, dans les compteurs de limitation.

## Tester les emails avec Mailpit

Après `docker compose up --build`, ouvrir l’application sur
<http://localhost:5173> et Mailpit sur <http://localhost:8025>. Le relais SMTP
local est `mailpit:1025` et n’expédie aucun message vers Internet.

1. Inscrire `investor@example.com`, ouvrir le premier email dans Mailpit et
   suivre son lien de vérification.
2. Se connecter, se déconnecter puis demander une réinitialisation depuis
   l’écran de connexion.
3. Ouvrir le second email dans Mailpit, suivre son lien et choisir un nouveau
   mot de passe.
4. Confirmer qu’une ancienne session ne résout plus `GET /api/v1/auth/me` et
   que le nouveau mot de passe permet la connexion.

Les liens locaux ciblent `MKVIP_PUBLIC_APP_URL=http://localhost:5173`.

## Migration du premier compte vérifié

La migration v0.9 crée un propriétaire système inactif et lui rattache toutes
les entreprises historiques. Lors de la toute première vérification d’adresse,
une transaction verrouille ce propriétaire, transfère toutes ses entreprises
au premier compte humain vérifié puis supprime le compte système. Une
inscription abandonnée ou non vérifiée ne peut donc pas revendiquer ces
données. Les comptes vérifiés suivants commencent avec un univers vide. Le
scénario de migration et la concurrence entre deux premières vérifications
sont validés sur PostgreSQL 17.

## Configuration de production et limites

Les valeurs Compose conviennent uniquement au développement local. En
production :

- servir frontend et API exclusivement en HTTPS et imposer
  `MKVIP_SESSION_COOKIE_SECURE=true` ;
- remplacer `MKVIP_AUTH_EMAIL_HASH_SECRET` par un secret HMAC fort, aléatoire,
  unique à l’environnement et géré hors du dépôt ;
- remplacer `MKVIP_MFA_ENCRYPTION_KEY` par une clé Fernet aléatoire et la
  sauvegarder durablement dans le gestionnaire de secrets ;
- utiliser un relais SMTP authentifié, renseigner
  `MKVIP_SMTP_USERNAME`/`MKVIP_SMTP_PASSWORD` et activer
  `MKVIP_SMTP_STARTTLS=true` ;
- configurer `MKVIP_PUBLIC_APP_URL` avec l’origine HTTPS publique exacte.

La limitation applicative des connexions est partagée par PostgreSQL entre les
instances MK-VIP. Elle doit être complétée en production par une limitation en
périphérie et un pare-feu applicatif afin de bloquer le trafic avant qu’il
n’atteigne l’API. Depuis v0.9.1, l’Analyste IA dispose d’un quota quotidien et
d’un cache persistant isolés par utilisateur. Les imports Yahoo disposent aussi
d’une admission locale par utilisateur et par entreprise ; une limite partagée
entre plusieurs instances reste à fournir par l’infrastructure.

Le déploiement VPS de référence, les fichiers secrets attendus et les
procédures de sauvegarde et de retour arrière sont détaillés dans
[`deployment-vps.md`](deployment-vps.md).

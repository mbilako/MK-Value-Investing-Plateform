# Authentification et isolation des données

MK-VIP v0.9 utilise des comptes personnels. Toutes les routes métier exigent
une session valide et chaque entreprise appartient à un seul utilisateur.

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

## Mots de passe et verrouillage

Les mots de passe ne sont jamais stockés en clair. Ils sont hachés avec
Argon2id par `pwdlib`. Après cinq échecs consécutifs
(`MKVIP_LOGIN_MAX_ATTEMPTS=5`), le compte est verrouillé pendant 15 minutes
(`MKVIP_LOGIN_LOCK_MINUTES=15`). Les réponses de connexion ne révèlent pas si
un compte existe, est inactif ou est verrouillé.

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

## Migration du premier compte

La migration v0.9 crée un propriétaire système inactif et lui rattache toutes
les entreprises historiques. Lors de la toute première inscription, une
transaction verrouille ce propriétaire, transfère toutes ses entreprises au
premier compte humain puis supprime le compte système. Les inscriptions
suivantes commencent avec un univers vide. Le scénario de migration et la
concurrence entre deux premières inscriptions sont validés sur PostgreSQL 17
dans l’intégration continue.

## Fonctions différées

La vérification d’adresse email, la réinitialisation du mot de passe,
l’authentification multifacteur et la limitation de débit au niveau de
l’infrastructure ne font pas partie de v0.9. Depuis la version 0.9.1,
l’Analyste IA dispose toutefois d’un quota quotidien et d’un cache persistant
isolés par utilisateur. Les imports Yahoo disposent également d’une admission
locale par utilisateur et par entreprise ; une limite partagée entre plusieurs
instances reste à fournir par l’infrastructure.

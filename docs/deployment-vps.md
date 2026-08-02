# Déploiement de MK-VIP sur un VPS

Ce runbook déploie MK-VIP sur une VM Linux avec Docker Compose. Caddy termine
automatiquement HTTPS, le frontend Nginx sert l’application et relaie l’API,
le backend FastAPI reste privé, et PostgreSQL n’est jamais publié sur Internet.

## 1. Préparer le serveur et le DNS

Le serveur doit disposer de Docker Engine, du module Docker Compose et de Git.
Le pare-feu doit autoriser SSH depuis les adresses d’administration ainsi que
les ports publics `80/tcp`, `443/tcp` et `443/udp`. Le port PostgreSQL ne doit
pas être ouvert.

Créer les enregistrements DNS `A` et, si nécessaire, `AAAA` du domaine avant
le premier démarrage. Caddy ne peut obtenir le certificat tant que le domaine
ne pointe pas vers le VPS.

## 2. Préparer la configuration

Depuis la racine du dépôt :

```sh
cp deploy/production.env.example deploy/.env.production
mkdir -p deploy/secrets
chmod 700 deploy/secrets
```

Modifier `deploy/.env.production` avec le domaine, l’adresse ACME et le relais
SMTP réels. Le fichier est ignoré par Git.

Générer des valeurs aléatoires compatibles avec une URL pour PostgreSQL et le
secret HMAC :

```sh
umask 077
openssl rand -hex 24 > deploy/secrets/postgres_password
openssl rand -hex 32 > deploy/secrets/auth_email_hash_secret
openssl rand -base64 32 | tr '+/' '-_' > deploy/secrets/mfa_encryption_key
```

Créer ensuite les trois secrets fournis par les services externes :

```sh
printf '%s' 'postgresql+asyncpg://mkvip:MOT_DE_PASSE@db:5432/mkvip' > deploy/secrets/database_url
printf '%s' 'CLE_OPENAI' > deploy/secrets/openai_api_key
printf '%s' 'MOT_DE_PASSE_SMTP' > deploy/secrets/smtp_password
chmod 600 deploy/secrets/*
```

Le mot de passe de `database_url` doit être identique au contenu de
`postgres_password`. Les valeurs générées en hexadécimal évitent la nécessité
d’encoder des caractères spéciaux dans l’URL.

La clé `mfa_encryption_key` chiffre les secrets TOTP déjà enregistrés. Elle
doit être sauvegardée hors du VPS et restaurée à l’identique après un incident.
La remplacer sans procédure de ré-encryption rendrait les MFA existants
illisibles.

## 3. Valider et déployer

```sh
docker compose \
  --env-file deploy/.env.production \
  -f compose.production.yml \
  config --quiet

sh deploy/deploy.sh
```

Le service `migrate` termine la migration Alembic avant le démarrage du
backend. Le déploiement doit rester limité à une seule exécution de migration à
la fois.

Contrôler ensuite :

```sh
docker compose --env-file deploy/.env.production -f compose.production.yml ps
sh deploy/smoke-test.sh https://invest.example.com
```

Les endpoints ont des rôles distincts :

- `/api/v1/health` confirme que le processus API répond ;
- `/api/v1/ready` confirme aussi que PostgreSQL accepte une requête.

## 4. Exploiter et diagnostiquer

Les accès HTTP et les requêtes API sont journalisés en JSON. Chaque réponse API
contient `X-Request-ID`, réutilisé lorsqu’un identifiant valide est fourni par
un proxy ou généré par le backend dans le cas contraire.

```sh
docker compose --env-file deploy/.env.production -f compose.production.yml logs --tail=200 caddy
docker compose --env-file deploy/.env.production -f compose.production.yml logs --tail=200 backend
docker compose --env-file deploy/.env.production -f compose.production.yml logs --tail=200 db
```

Une supervision externe doit appeler `/api/v1/health` et `/api/v1/ready`. Une
alerte est nécessaire si la disponibilité échoue deux fois de suite ou si le
taux de réponses `5xx` augmente.

## 5. Sauvegarder et vérifier la restauration

Créer une sauvegarde avant chaque mise à niveau et au moins quotidiennement :

```sh
sh deploy/backup.sh
```

Le chemin du fichier `.dump` est affiché à la fin. Copier ce fichier chiffré
vers un stockage distinct du VPS et définir une politique de rétention.

La restauration doit d’abord être répétée dans une base isolée :

```sh
docker compose --env-file deploy/.env.production -f compose.production.yml exec db \
  sh -c 'createdb -U "$POSTGRES_USER" mkvip_restore_check'

docker compose --env-file deploy/.env.production -f compose.production.yml exec -T db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d mkvip_restore_check --no-owner --no-privileges' \
  < backups/mkvip-AAAAmmjjTHHMMSSZ.dump

docker compose --env-file deploy/.env.production -f compose.production.yml exec db \
  sh -c 'psql -U "$POSTGRES_USER" -d mkvip_restore_check -c "SELECT version_num FROM alembic_version"'

docker compose --env-file deploy/.env.production -f compose.production.yml exec db \
  sh -c 'dropdb -U "$POSTGRES_USER" mkvip_restore_check'
```

Une restauration de production est une opération destructive. Elle exige une
fenêtre d’intervention, une sauvegarde préalable et une validation explicite
du fichier et de la base cible.

## 6. Mettre à niveau et revenir en arrière

Avant une mise à niveau :

1. exécuter `sh deploy/backup.sh` ;
2. lire les notes de version et les migrations ;
3. déployer d’abord sur staging ;
4. lancer le test de fumée ;
5. promouvoir le même tag en production.

Le retour applicatif consiste à redéployer le tag Git précédent. Le retour de
schéma n’est pas automatique : il ne doit être lancé que si la migration le
permet sans perte et après sauvegarde vérifiée.

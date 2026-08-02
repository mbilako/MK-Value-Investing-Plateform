# Secrets de production

Ce dossier ne doit contenir que des fichiers créés directement sur le serveur.
Leur contenu ne doit jamais être ajouté à Git.

Fichiers attendus :

- `postgres_password` : mot de passe PostgreSQL aléatoire ;
- `database_url` : URL complète `postgresql+asyncpg://...` utilisant le même mot de passe ;
- `openai_api_key` : clé API OpenAI ;
- `auth_email_hash_secret` : secret HMAC aléatoire d’au moins 32 octets ;
- `mfa_encryption_key` : clé Fernet générée une seule fois et sauvegardée durablement ;
- `smtp_password` : mot de passe du relais SMTP.

Chaque fichier doit contenir uniquement la valeur, suivie éventuellement d’un saut de ligne,
et être lisible uniquement par le compte qui exploite MK-VIP.

# Analyste IA v0.8

## Objectif

L’Analyste IA aide à lire les résultats déjà produits par MK Value Investing
Platform. Il ne remplace ni les calculs financiers, ni les publications
réglementaires, ni le jugement de l’investisseur.

Trois modes sont disponibles :

- `summary` produit une synthèse d’un dossier ;
- `comparison` compare deux entreprises distinctes ;
- `question` répond à une question naturelle ciblée.

## Contrat API

```http
POST /api/v1/ai/analyses
Content-Type: application/json
```

```json
{
  "mode": "comparison",
  "company_id": "uuid",
  "comparison_company_id": "uuid"
}
```

La réponse contient une conclusion, des constats sourcés, des risques, les
informations manquantes, les sources disponibles, le modèle et un
avertissement. Une question doit contenir de 3 à 800 caractères. Une
comparaison exige deux entreprises différentes.

## Contexte transmis

Pour chaque entreprise, l’API charge :

- la dernière analyse financière, obligatoire ;
- la dernière valorisation, lorsqu’elle existe ;
- le dernier scoring global, lorsqu’il existe.

Chaque objet reçoit un identifiant interne tel que `financial:<uuid>`,
`valuation:<uuid>` ou `scoring:<uuid>`. Toute citation produite par le
fournisseur qui ne correspond pas à cette liste provoque une réponse `502` au
lieu d’être affichée.

## Garde-fous

- Le modèle n’a accès ni au Web ni à un outil externe.
- Les valeurs JSON sont des données et ne peuvent pas redéfinir les
  instructions.
- Les informations absentes doivent être signalées, jamais inventées.
- Chaque constat doit citer au moins une source MK-VIP.
- Aucune recommandation d’achat, de vente ou d’allocation n’est autorisée.
- La sortie est contrainte par un schéma JSON strict, puis validée une seconde
  fois par Pydantic.
- Les tests utilisent un faux fournisseur et n’effectuent aucun appel payant.

## Configuration

La clé locale est stockée dans `.env.local`, exclu du dépôt :

```dotenv
OPENAI_API_KEY=<secret local>
MKVIP_OPENAI_MODEL=gpt-5.6-sol
```

Le fournisseur suit les recommandations officielles relatives à
[l’API Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses)
et aux
[sorties structurées](https://developers.openai.com/api/docs/guides/structured-outputs).
Le modèle par défaut peut être changé par configuration sans modifier le
contrat MK-VIP.

## Limites

La v0.8 produit les analyses à la demande sans les persister. Elle ne gère pas
encore l’authentification, les quotas par utilisateur, la mise en cache ou la
reprise d’une analyse précédente. Les sources présentées restent des objets
MK-VIP ; l’utilisateur doit toujours rapprocher les données de la publication
réglementaire originale.

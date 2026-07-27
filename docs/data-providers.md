# Fournisseurs de données financières

## Contrat commun

Le moteur MK‑VIP ne dépend jamais directement d’une API externe.
`FinancialDataProvider` expose la recherche, le profil, les trois états
financiers annuels et l’historique des prix. Chaque fournisseur traduit ses
libellés vers les objets canoniques du domaine.

## Yahoo Finance

Le premier connecteur utilise `yfinance` sans clé API. Pour une entreprise
comme Air Liquide, le ticker attendu est `AI.PA`.

| Donnée MK‑VIP | Libellés Yahoo acceptés |
|---|---|
| Chiffre d’affaires | `TotalRevenue`, `OperatingRevenue` |
| EBITDA | `EBITDA`, `NormalizedEBITDA` |
| Amortissements | `DepreciationAndAmortizationInIncomeStatement`, `DepreciationAndAmortization` |
| EBIT | `EBIT`, `OperatingIncome` |
| Charges d’intérêts | `InterestExpenseNonOperating`, `InterestExpense`, `NetNonOperatingInterestIncomeExpense` |
| Résultat net | `NetIncome`, `NetIncomeCommonStockholders` |
| Total actif | `TotalAssets` |
| Actif circulant | `CurrentAssets`, `TotalCurrentAssets` |
| Passif exigible | `CurrentLiabilities`, `TotalCurrentLiabilities` |
| Dette financière | `TotalDebt` |
| Trésorerie | `CashCashEquivalentsAndShortTermInvestments`, `CashAndCashEquivalents` |
| Capitaux propres | `StockholdersEquity`, `TotalEquityGrossMinorityInterest` |
| Investissements | `CapitalExpenditure`, `PurchaseOfPPE` |
| Flux de trésorerie opérationnel | `OperatingCashFlow`, `TotalCashFromOperatingActivities` |

Le normalisateur conserve le dernier exercice complet présent dans le compte
de résultat, le bilan et le tableau de flux. Les exercices historiques
incomplets sont ignorés. Les montants sont divisés par un million ; les charges
d’intérêts, amortissements et investissements sont convertis en valeurs
absolues avant le calcul des ratios.

## Capacité et délais

Les opérations synchrones de `yfinance` sont exécutées dans un pool dédié,
limité à huit appels par défaut. Lorsque toutes les places sont occupées, une
nouvelle opération échoue immédiatement au lieu de rejoindre une file
d’attente non bornée. Une place n’est libérée qu’à la fin réelle du thread,
même si la réponse HTTP a déjà dépassé son délai.

Chaque appel Yahoo dispose d’un délai logique de 10 secondes et les quatre
opérations d’un import partagent un délai global de 30 secondes. Un utilisateur
ne peut lancer qu’un import automatique à la fois et une entreprise ne peut
avoir deux imports concurrents. Ces valeurs sont configurables avec :

```dotenv
MKVIP_YAHOO_MAX_CONCURRENCY=8
MKVIP_YAHOO_RESPONSE_TIMEOUT_SECONDS=10
MKVIP_YAHOO_IMPORT_TIMEOUT_SECONDS=30
MKVIP_YAHOO_IMPORTS_PER_USER=1
```

L’admission par utilisateur et par entreprise est maintenue en mémoire dans
chaque instance de l’API. Un déploiement horizontal doit donc compléter cette
protection avec une limite distribuée partagée entre les instances.

## Traçabilité et limites

La source persistée prend la forme
`Yahoo Finance · <ticker> · exercice <année>`. Un import est refusé lorsqu’aucun
exercice complet ne peut être normalisé ou lorsque l’exercice retenu existe
déjà.

`yfinance` n’est pas affilié à Yahoo. Les API publiques de Yahoo Finance sont
destinées à la recherche et à un usage personnel. Les chiffres doivent être
validés contre le rapport annuel audité ou le dépôt réglementaire avant toute
décision d’investissement.

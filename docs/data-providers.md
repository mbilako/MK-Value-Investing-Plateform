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

Le normalisateur conserve le dernier exercice complet présent dans le compte
de résultat, le bilan et le tableau de flux. Les exercices historiques
incomplets sont ignorés. Les montants sont divisés par un million ; les charges
d’intérêts, amortissements et investissements sont convertis en valeurs
absolues avant le calcul des ratios.

## Traçabilité et limites

La source persistée prend la forme
`Yahoo Finance · <ticker> · exercice <année>`. Un import est refusé lorsqu’aucun
exercice complet ne peut être normalisé ou lorsque l’exercice retenu existe
déjà.

`yfinance` n’est pas affilié à Yahoo. Les API publiques de Yahoo Finance sont
destinées à la recherche et à un usage personnel. Les chiffres doivent être
validés contre le rapport annuel audité ou le dépôt réglementaire avant toute
décision d’investissement.

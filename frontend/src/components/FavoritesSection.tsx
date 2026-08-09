import { ArrowRight, Star } from "lucide-react";

import type { Company } from "../api/client";

interface FavoritesSectionProps {
  companies: Company[];
  scores: Record<string, number>;
  onAnalysis: (company: Company) => void;
  onRemove: (company: Company) => void;
}

export function FavoritesSection({
  companies,
  scores,
  onAnalysis,
  onRemove,
}: FavoritesSectionProps) {
  const favorites = companies.filter((company) => company.is_favorite);

  return (
    <section
      className="section favorites-section"
      id="favorites"
      aria-labelledby="favorites-title"
    >
      <div className="favorites-heading">
        <div>
          <p className="section-eyebrow">Sélection personnelle</p>
          <h2 id="favorites-title">Favoris</h2>
        </div>
        <span>
          {favorites.length} entreprise{favorites.length > 1 ? "s" : ""}
        </span>
      </div>
      {favorites.length ? (
        <div className="favorites-grid">
          {favorites.map((company) => {
            const score = scores[company.id] ?? company.latest_mk_score;
            return (
              <article className="favorite-card" key={company.id}>
                <button
                  className="favorite-card__star"
                  onClick={() => onRemove(company)}
                  aria-label={`Retirer ${company.name} des favoris`}
                  title="Retirer des favoris"
                >
                  <Star aria-hidden="true" size={18} fill="currentColor" />
                </button>
                <div>
                  <strong>{company.name}</strong>
                  <span>
                    {company.ticker} · {company.country}
                  </span>
                </div>
                <p>
                  MK Score <strong>{score ?? "—"}</strong>
                </p>
                <button
                  className="favorite-card__open"
                  onClick={() => onAnalysis(company)}
                >
                  Voir l’analyse
                  <ArrowRight aria-hidden="true" size={16} />
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="favorites-empty">
          <Star aria-hidden="true" size={28} />
          <p>
            Après avoir calculé un MK Score, utilisez l’étoile dans la liste des
            entreprises pour conserver votre sélection ici.
          </p>
        </div>
      )}
    </section>
  );
}

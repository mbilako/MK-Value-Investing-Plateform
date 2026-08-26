import { useState } from "react";
import {
  BarChart3,
  BookOpen,
  Building2,
  Home,
  ListFilter,
  ScanSearch,
  SlidersHorizontal,
  Star,
} from "lucide-react";

const navigation = [
  { label: "Vue d’ensemble", icon: Home, href: "#overview" },
  { label: "Sélection", icon: ListFilter, href: "#screener" },
  { label: "Scan de marché", icon: ScanSearch, href: "#market-scanner" },
  { label: "Entreprises", icon: Building2, href: "#companies" },
  { label: "Favoris", icon: Star, href: "#favorites" },
  { label: "Analyses", icon: BarChart3, href: "#analyses" },
  { label: "Règles", icon: SlidersHorizontal, href: "#rules" },
  { label: "Journal", icon: BookOpen, href: "#journal" },
];

export function Sidebar() {
  const [activeHref, setActiveHref] = useState("#overview");
  return (
    <aside className="sidebar">
      <a className="brand" href="#overview" aria-label="MK-VIP — Accueil">
        <span className="brand__name">MK-VIP</span>
        <span className="brand__description">MK Value Investing Platform</span>
      </a>
      <nav aria-label="Navigation principale">
        <ul className="sidebar__nav">
          {navigation.map(({ label, icon: Icon, href }) => (
            <li key={label}>
              <a
                className="nav-item"
                data-current={activeHref === href || undefined}
                href={href}
                aria-current={activeHref === href ? "location" : undefined}
                onClick={() => setActiveHref(href)}
              >
                <Icon aria-hidden="true" size={20} strokeWidth={1.75} />
                <span>{label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar__foot">
        <span className="status-dot" aria-hidden="true" />
        Version 0.12 Indices internationaux
      </div>
    </aside>
  );
}

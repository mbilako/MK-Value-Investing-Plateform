import {
  BarChart3,
  BookOpen,
  Building2,
  Home,
  SlidersHorizontal,
} from "lucide-react";

const navigation = [
  { label: "Vue d’ensemble", icon: Home, current: true },
  { label: "Entreprises", icon: Building2 },
  { label: "Analyses", icon: BarChart3 },
  { label: "Règles", icon: SlidersHorizontal },
  { label: "Journal", icon: BookOpen },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="MK-VIP — Accueil">
        <span className="brand__name">MK-VIP</span>
        <span className="brand__description">MK Value Investing Platform</span>
      </a>
      <nav aria-label="Navigation principale">
        <ul className="sidebar__nav">
          {navigation.map(({ label, icon: Icon, current }) => (
            <li key={label}>
              <a
                className="nav-item"
                data-current={current || undefined}
                href={current ? "/" : "#"}
                aria-current={current ? "page" : undefined}
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
        Version 0.9 Comptes personnels
      </div>
    </aside>
  );
}
